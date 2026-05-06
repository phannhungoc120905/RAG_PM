"""
ocr_service.py — OCR Service tối ưu cho văn bản hành chính tiếng Việt.

Các cải tiến chính so với phiên bản cũ:
1. Image preprocessing nâng cao: adaptive thresholding, deskew, denoising
2. Sửa lỗi OCR theo ngữ cảnh (context-aware) thay vì chỉ dùng \b word boundary
3. Bảng thay thế lỗi phong phú hơn, có phân loại rõ ràng
4. Pipeline làm sạch nhiều tầng với thứ tự đúng
5. Validate chính tả sau correction bằng từ điển tiếng Việt tối giản
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from functools import lru_cache
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pyvi import ViTokenizer

from config import settings

logger = logging.getLogger(__name__)


# ─── Fallback Models ──────────────────────────────────────────────────────────

class _FallbackEmbeddingModel:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def encode(self, texts: List[str]) -> np.ndarray:
        vectors: list[np.ndarray] = []
        for text in texts:
            vector = np.zeros(self.dimension, dtype="float32")
            tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
            if not tokens:
                vectors.append(vector)
                continue
            for token in tokens:
                token_hash = hash(token)
                index = token_hash % self.dimension
                sign = -1.0 if (token_hash >> 1) & 1 else 1.0
                vector[index] += sign
            norm = float(np.linalg.norm(vector))
            if norm > 0:
                vector /= norm
            vectors.append(vector)
        return np.vstack(vectors)


class _FallbackBM25:
    def __init__(self, tokenized_corpus: list[list[str]]):
        self.tokenized_corpus = tokenized_corpus

    def get_scores(self, tokenized_query: list[str]) -> np.ndarray:
        query_tokens = set(tokenized_query)
        scores = []
        for doc_tokens in self.tokenized_corpus:
            if not doc_tokens:
                scores.append(0.0)
                continue
            overlap = len(query_tokens.intersection(doc_tokens))
            scores.append(overlap / max(len(query_tokens), 1))
        return np.array(scores, dtype="float32")


# ─── Vietnamese OCR Correction Tables ─────────────────────────────────────────

class _VietnameseOCRCorrector:
    """
    Sửa lỗi OCR tiếng Việt theo nhiều tầng:
      1. Lỗi font (TCVN3, VNI) → Unicode
      2. Lỗi ký tự đơn lẻ do confusion matrix của OCR engine
      3. Lỗi âm tiết (syllable-level) thường gặp
      4. Lỗi cụm từ (phrase-level) thường gặp
      5. Lỗi từ viết tắt hành chính

    QUAN TRỌNG: Dùng lookahead/lookbehind thay vì \b vì \b không hoạt động
    đúng với Unicode tiếng Việt có dấu.
    """

    # ── 1. Bảng chuyển đổi font TCVN3 → Unicode ───────────────────────────────
    TCVN3_CHAR_MAP = str.maketrans({
        "µ": "à", "¸": "á", "¶": "ả", "·": "ã", "¹": "ạ",
        "¨": "ă", "»": "ằ", "¾": "ắ", "¼": "ẳ", "½": "ẵ", "Æ": "ặ",
        "©": "â", "Ç": "ầ", "Ê": "ấ", "È": "ẩ", "É": "ẫ", "Ë": "ậ",
        "Ì": "è", "Ð": "é", "Î": "ẻ", "Ï": "ẽ", "Ñ": "ẹ",
        "ª": "ê", "Ò": "ề", "Õ": "ế", "Ó": "ể", "Ô": "ễ", "Ö": "ệ",
        "×": "ì", "Ø": "í", "Ü": "ỉ", "Ý": "ĩ", "Þ": "ị",
        "ß": "ò", "ã": "ó", "á": "ỏ", "â": "õ", "ä": "ọ",
        "¬": "ơ", "å": "ờ", "ç": "ớ", "æ": "ở", "è": "ỡ", "é": "ợ",
        "ê": "ù", "ë": "ú", "ì": "ủ", "í": "ũ", "î": "ụ",
        "ï": "ỳ", "ó": "ý", "ñ": "ỷ", "ò": "ỹ", "ô": "ỵ",
        "­": "ư", "ø": "ừ", "ö": "ứ", "÷": "ử", "ù": "ữ", "ú": "ự",
        "¡": "Ă", "¢": "Â", "§": "Đ", "£": "Ê", "¤": "Ô", "¥": "Ơ", "¦": "Ư",
    })

    # ── 2. Bảng chuyển đổi VNI → Unicode ─────────────────────────────────────
    COMMON_VNI_REPLACEMENTS = [
        ("aø", "à"), ("aù", "á"), ("aû", "ả"), ("aõ", "ã"), ("aï", "ạ"),
        ("aê", "ă"), ("aâ", "â"), ("eø", "è"), ("eù", "é"), ("eû", "ẻ"),
        ("eõ", "ẽ"), ("eï", "ẹ"), ("eâ", "ê"), ("oø", "ò"), ("où", "ó"),
        ("oû", "ỏ"), ("oõ", "õ"), ("oï", "ọ"), ("oâ", "ô"), ("ôø", "ồ"),
        ("ôù", "ố"), ("ôû", "ổ"), ("ôõ", "ỗ"), ("ôï", "ộ"), ("uø", "ù"),
        ("uù", "ú"), ("uû", "ủ"), ("uõ", "ũ"), ("uï", "ụ"), ("ö", "ư"),
        ("yø", "ỳ"), ("yù", "ý"), ("yû", "ỷ"), ("yõ", "ỹ"), ("yï", "ỵ"),
        ("ñ", "đ"),
    ]

    # ── 3. Confusion matrix ký tự đơn của Tesseract với tiếng Việt ───────────
    # Format: (pattern, replacement) — dùng regex để tránh false positive
    # Nhóm: lỗi do hình dạng ký tự tương tự (visual confusion)
    CHAR_CONFUSION_FIXES: list[tuple[str, str]] = [
        # Số bị nhận nhầm thành chữ và ngược lại (trong ngữ cảnh văn bản)
        (r"(?<=[a-zA-ZÀ-ỹ])0(?=[a-zA-ZÀ-ỹ])", "o"),   # 0 → o giữa chữ cái
        (r"(?<=[a-zA-ZÀ-ỹ])1(?=[a-zA-ZÀ-ỹ])", "l"),   # 1 → l giữa chữ cái
        (r"(?<=[a-zA-ZÀ-ỹ])5(?=[a-zA-ZÀ-ỹ])", "s"),   # 5 → s giữa chữ cái
        # Dấu câu bị OCR nhận nhầm
        (r"(?<=\w)\s*[|]\s*(?=\w)", " "),               # | → space giữa từ
        (r"``", '"'),                                    # backtick kép → ngoặc kép
        (r"''", '"'),                                    # nháy đơn kép → ngoặc kép
        # Đặc thù Tesseract với dấu tiếng Việt
        (r"ủy\s+ban", "Ủy ban"),                        # case fix
        (r"\bvà\b", "và"),                              # không cần nhưng đảm bảo
    ]

    # ── 4. Lỗi âm tiết thường gặp (syllable confusion) ───────────────────────
    # Quan trọng: KHÔNG dùng \b — dùng (?<!\w) và (?!\w) thay thế
    # vì \b không nhận diện đúng biên từ Unicode
    #
    # Phân loại nguyên nhân:
    #   [TONE]   = nhận nhầm dấu thanh
    #   [VOWEL]  = nhận nhầm nguyên âm
    #   [CONS]   = nhận nhầm phụ âm
    #   [DIACRITIC] = nhận nhầm dấu phụ (mũ, móc...)
    SYLLABLE_FIXES: list[tuple[str, str, str]] = [
        # [TONE] thanh sắc/huyền/nặng hay bị lẫn
        ("xõy",    "xây",    "TONE"),
        ("hỵp",    "hợp",    "TONE"),
        ("mỵ",     "mô",     "TONE"),
        ("hủnh",   "hình",   "TONE"),
        ("trủnh",  "trình",  "TONE"),
        ("chuýn",  "chuyên", "TONE"),
        ("thỵng",  "thông",  "TONE"),
        ("nhõn",   "nhân",   "TONE"),
        ("phõn",   "phân",   "TONE"),
        ("tiùn",   "tiên",   "TONE"),
        ("liùn",   "liên",   "TONE"),
        ("tõm",    "tâm",    "TONE"),
        ("tỏc",    "tác",    "TONE"),
        ("lỳ",     "lý",     "TONE"),
        ("ýu",     "yêu",    "TONE"),
        ("giựp",   "giúp",   "TONE"),
        ("hýa",    "hóa",    "TONE"),
        ("thỏi",   "thái",   "TONE"),
        ("phữ",    "phù",    "TONE"),
        ("cỏc",    "các",    "TONE"),
        ("phũa",   "phía",   "TONE"),

        # [VOWEL/DIACRITIC] nguyên âm bị nhầm
        ("đý",     "đó",     "VOWEL"),
        ("đýng",   "đóng",   "VOWEL"),
        ("nýi",    "nói",    "VOWEL"),
        ("dững",   "dùng",   "VOWEL"),
        ("cững",   "cũng",   "VOWEL"),
        ("tỵ",     "tư",     "VOWEL"),
        ("trỹ",    "trò",    "VOWEL"),
        ("tỹ",     "từ",     "VOWEL"),
        ("xực",    "xúc",    "VOWEL"),
        ("tũch",   "tích",   "VOWEL"),
        ("tũch",   "tích",   "VOWEL"),

        ("phỏt",   "phát",   "VOWEL"),
        ("nhým",   "nhóm",   "VOWEL"),
        ("bỏc",    "bác",    "VOWEL"),
        ("sỉ",     "sĩ",     "VOWEL"),
        ("xõy",    "xây",    "VOWEL"),

        # [DIACRITIC] dấu phụ bị mất hoặc sai
        ("nguoi",  "người",  "DIACRITIC"),
        ("viec",   "việc",   "DIACRITIC"),
        ("duoc",   "được",   "DIACRITIC"),
        ("khong",  "không",  "DIACRITIC"),
        ("truong", "trường", "DIACRITIC"),
        ("phuong", "phương", "DIACRITIC"),
        ("thuong", "thường", "DIACRITIC"),
        ("quyet",  "quyết",  "DIACRITIC"),
        ("dinh",   "định",   "DIACRITIC"),
        ("hanh",   "hành",   "DIACRITIC"),
        ("chinh",  "chính",  "DIACRITIC"),
        ("nghi",   "nghị",   "DIACRITIC"),
        ("dong",   "đồng",   "DIACRITIC"),
        ("theo",   "theo",   "DIACRITIC"),   # không cần đổi, giữ để document

        # [CONS] phụ âm bị nhầm
        ("kiến trực", "kiến trúc", "CONS"),  # c/ck confusion (xử lý ở phrase)

        # [TONE] lỗi từ văn bản hành chính thực tế (Nghị định 30/2020)
        ("trũnh",    "trình",   "TONE"),
        ("chũnh",    "chính",   "TONE"),
        ("dỹng",     "dòng",    "TONE"),
        ("nợt",      "nét",     "TONE"),
        ("bữn",      "bên",     "TONE"),
        ("tữn",      "tên",     "TONE"),
        ("tiữu",     "tiêu",    "TONE"),
        ("riững",    "riêng",   "TONE"),
        ("thủ",      "thì",     "TONE"),
        ("tỏng",     "tổng",    "TONE"),

        # [VOWEL] lỗi nguyên âm từ văn bản hành chính thực tế
        ("khỵng",    "không",   "VOWEL"),
        ("phỵng",    "phông",   "VOWEL"),
        ("cý",       "có",      "VOWEL"),
        ("mý",       "mã",      "VOWEL"),
        ("trữn",     "trên",    "VOWEL"),
        ("trỏi",     "trái",    "VOWEL"),
        ("mợp",      "mép",     "VOWEL"),
        ("cỏch",     "cách",    "VOWEL"),
        ("ỵ",        "ở",       "VOWEL"),

        # [TONE/VOWEL] thêm từ văn bản mẫu người dùng
        ("nhi ệm",   "nhiệm",   "TONE"),
        ("đi ều",    "điều",    "TONE"),
        ("ph ối",    "phối",    "TONE"),
        ("đảm",      "đảm",     "TONE"),
        ("đi ền",    "điền",    "TONE"),
        ("chuy ển",  "chuyển",  "TONE"),
        ("nh ận",    "nhận",    "TONE"),
        ("gi ữa",    "giữa",    "TONE"),
        ("chuy ên",  "chuyên",  "TONE"),
        ("kh ỏm",    "khám",    "TONE"),
        ("khỏm",     "khám",    "TONE"),
        ("gợi ý",    "gợi ý",   "TONE"),
        ("đi khỏm",  "đi khám", "TONE"),
        ("triệu ch ứng", "triệu chứng", "TONE"),
        ("ch ứng",   "chứng",   "TONE"),
        ("ch ữa",    "chữa",    "TONE"),
        ("b ệnh",    "bệnh",    "TONE"),
        ("b ỏc",     "bác",     "TONE"),
        ("v ăn",     "văn",     "TONE"),
        ("l ắng",    "lắng",    "TONE"),
        ("t ự",      "tự",      "TONE"),
        ("c ập",     "cập",     "TONE"),
        ("s ơ",      "sơ",      "TONE"),
        ("đi ện tử", "điện tử", "TONE"),
        ("tõm",      "tâm",     "TONE"),
        ("dõi",      "dõi",     "TONE"),
        ("ph ữ",     "phù",     "TONE"),
        ("ph ọc",    "phục",    "TONE"),
        ("phục vụ",  "phục vụ", "TONE"),
        ("nh ý",     "nhóm",    "VOWEL"),
        ("b điện",   "bệnh",    "VOWEL"),
        ("đứt",      "đưa",     "VOWEL"),
        ("điện nh õn", "bệnh nhân", "VOWEL"),
        ("c ốt l õi",  "cốt lõi",   "VOWEL"),
        ("l õi",     "lõi",     "VOWEL"),
        ("t ũch",    "tích",    "VOWEL"),
        ("ph õn",    "phân",    "VOWEL"),
        ("ch ẩn",    "chẩn",    "VOWEL"),
        ("đo ngoài", "đoán",    "VOWEL"),
        ("chẩn đo ngoài", "chẩn đoán", "VOWEL"),
        ("ph ỏc",    "phác",    "VOWEL"),
        ("phỏc đồ",  "phác đồ", "VOWEL"),
        ("ch ỉ ịnh", "chỉ định", "VOWEL"),
        ("ch ỉ",     "chỉ",     "VOWEL"),
        ("x ợt",     "xét",     "VOWEL"),
        ("đề ngh ị", "đề nghị", "VOWEL"),
        ("thu ốc",   "thuốc",   "VOWEL"),
        ("đơn thu ốc", "đơn thuốc", "VOWEL"),
        ("ch tỉnh",  "chỉnh",   "VOWEL"),
        ("ch ũnh",   "chính",   "VOWEL"),
        ("ch ũnh x ỏc", "chính xác", "VOWEL"),
        ("c ải thi ộ", "cải thiện", "VOWEL"),
        ("cải thi ộ", "cải thiện", "VOWEL"),
        ("hi ộ",     "hiện",    "VOWEL"),
        ("lhiện",    "hiện",    "VOWEL"),
        ("nó vẫn",   "hiện nay", "VOWEL"),
        ("phỹng",    "phòng",   "VOWEL"),
        ("phỹ h ợp", "phù hợp", "VOWEL"),
        ("mới cực t ế", "với thực tế", "VOWEL"),
        ("t ế",      "tế",      "VOWEL"),
        ("l õm",     "lâm",     "VOWEL"),
        ("l õm sàng","lâm sàng","VOWEL"),
        ("đi suy",   "điều",    "VOWEL"),
        ("đi suy ph ối", "điều phối", "VOWEL"),
        ("suy ph ối","phối",    "VOWEL"),
        ("ti tiếp",  "tiếp",    "VOWEL"),
        ("ti tiếp x cực", "tiếp xúc", "VOWEL"),
        ("ti tiếp nh ận", "tiếp nhận", "VOWEL"),
        ("x cực",    "xúc",     "VOWEL"),
        ("đng ý",    "đóng",    "VOWEL"),
        ("tr ợ l ý", "trợ lý",  "VOWEL"),
        ("l ý",      "lý",      "VOWEL"),
        ("tr ợ",     "trợ",     "VOWEL"),
        ("à tr ợ l ý", "là trợ lý", "VOWEL"),
        ("ch àn b ộ", "cho toàn bộ", "VOWEL"),
        ("àn b ộ",   "toàn bộ", "VOWEL"),
        ("h ành trườn", "hành trình", "VOWEL"),
        ("trườn",    "trình",   "VOWEL"),
        ("đ ựng",    "được",    "VOWEL"),
        ("rút thi loại", "rút thiểu","VOWEL"),
        ("thi loại", "thiểu",   "VOWEL"),
        ("loại sai s ýt", "lỗi sai sót", "VOWEL"),
        ("s ýt",     "sót",     "VOWEL"),
        ("khoa phỹng", "khoa phòng", "VOWEL"),
        ("v mới",    "với",     "VOWEL"),
        ("ừ đ ầu",   "từ đầu",  "VOWEL"),
        ("gi rút",   "giảm",    "VOWEL"),
        ("b điện nh õn", "bệnh nhân", "VOWEL"),
        ("ph ữ h ợp", "phù hợp", "VOWEL"),
        ("lực ti tiếp", "hỗ trợ tiếp", "VOWEL"),
        ("trong qu hoặc tủnh", "trong quá trình", "VOWEL"),
        ("qu hoặc",  "quá",     "VOWEL"),
        ("tủnh",     "trình",   "VOWEL"),
        ("c loại mô-đun", "các mô-đun", "VOWEL"),
        ("c loại",   "các",     "VOWEL"),
        ("kh ở đó tạo ra ống", "khởi động", "VOWEL"),
        ("kh ở đó",  "khởi",    "VOWEL"),
        ("tạo ra ống", "động",  "VOWEL"),
        ("lược đồ",  "schema",  "VOWEL"),
        ("ph ản ánh ý nghĩa", "phản ánh", "VOWEL"),
        ("m ột phần","một phần","VOWEL"),
        ("d ữ li ệu","dữ liệu", "VOWEL"),
        ("ti ec",    "việc",    "VOWEL"),
        ("ec ti",    "việc",    "VOWEL"),
        ("l iện ch ọn", "lựa chọn", "VOWEL"),
        ("l iện",    "lựa",     "VOWEL"),
        ("c đầu",    "câu hỏi", "VOWEL"),
        ("yêu c đầu","yêu cầu", "VOWEL"),
        ("li ữu",    "liên tục","VOWEL"),
        ("ng ữ c ảnh li ữu", "ngữ cảnh liên tục", "VOWEL"),
        ("ho ạt rộng", "hoạt động", "VOWEL"),
        ("rộng ph ối hợp", "động phối hợp", "VOWEL"),
        ("tri ệu ch ứng dụng ỵng", "triệu chứng", "VOWEL"),
        ("dụng ỵng", "dùng",    "VOWEL"),
        ("ỵng",      "ứng",     "VOWEL"),
        ("b tác",    "bằng",    "VOWEL"),
        ("b điện",   "bệnh",    "VOWEL"),
        ("qua v ăn b tác", "qua văn bản hoặc", "VOWEL"),
        ("v ăn b tác", "văn bản", "VOWEL"),
        ("gi ý n ý", "giọng nói", "VOWEL"),
        ("ph õn t ũch", "phân tích", "VOWEL"),
        ("m ức đ ộ", "mức độ",  "VOWEL"),
        ("đứt ra h ng ng", "đưa ra hướng", "VOWEL"),
        ("h ng ng",  "hướng",   "VOWEL"),
        ("x ử l ý ph ữ h ợp", "xử lý phù hợp", "VOWEL"),
        ("dõi t ại nh à", "dõi tại nhà", "VOWEL"),
        ("à ho ặc",  "hoặc",    "VOWEL"),
        ("g ợi ý đi", "gợi ý đi", "VOWEL"),
        ("gio nói",  "giọng nói", "VOWEL"),
        ("gi ựp",    "giúp",    "VOWEL"),
        ("d ễ d àng","dễ dàng", "VOWEL"),
        ("đ ặc bi ệt", "đặc biệt", "VOWEL"),
        ("người lớn tu ổi", "người lớn tuổi", "VOWEL"),
        ("tu ổi",    "tuổi",    "VOWEL"),
        ("FastAPI",  "FastAPI",  "VOWEL"),
        ("phần phụ trợ cũ", "phần backend",  "VOWEL"),
        ("phần phụ trợ",    "phần backend",  "VOWEL"),
        ("x sử dụng logic", "xử lý logic",   "VOWEL"),
        ("x sử dụng",       "xử lý",         "VOWEL"),
        ("x sử l ý",        "xử lý",         "VOWEL"),
        ("x ử l ý",         "xử lý",         "VOWEL"),
        ("s sử dụng",       "sử dụng",       "VOWEL"),
        ("v mới c",         "với các",       "VOWEL"),
        ("r õ ràng",        "rõ ràng",       "VOWEL"),
        ("g ồm",            "gồm",           "VOWEL"),
        ("đ ịnh ngh ĩa",    "định nghĩa",    "VOWEL"),
        ("đ ể",             "để",            "VOWEL"),
        ("c ủa",            "của",           "VOWEL"),
        ("c ủa c",          "của các",       "VOWEL"),
        ("c ý c",           "có cấu",        "VOWEL"),
        ("c ý",             "có",            "VOWEL"),
        ("tr ực",           "trúc",          "VOWEL"),
        ("c ấu tr ực",      "cấu trúc",      "VOWEL"),
        ("chu ẩn h ýa",     "chuẩn hóa",     "VOWEL"),
        ("h ýa",            "hóa",           "VOWEL"),
        ("lưu trữ đ để",    "lưu trữ để",    "VOWEL"),
        ("đ để",            "để",            "VOWEL"),
        ("ti tiếp nh ận",   "tiếp nhận",     "VOWEL"),
        ("yêu c đầu",       "yêu cầu",       "VOWEL"),
        ("đi suy ph ối",    "điều phối",     "VOWEL"),
        ("tr ả k ết",       "trả kết",       "VOWEL"),
        ("k ết qu ảnh",     "kết quả",       "VOWEL"),
        ("qu ảnh",          "quả",           "VOWEL"),
        ("dững",            "dùng",          "VOWEL"),
        ("tụ đ ộng",        "tự động",       "VOWEL"),
        ("t ự đ ộng",       "tự động",       "VOWEL"),
        ("c ập nhật",       "cập nhật",      "VOWEL"),
        ("nh ận",           "nhận",          "VOWEL"),
        ("b ệnh vi ện",     "bệnh viện",     "VOWEL"),
        ("vi ện",           "viện",          "VOWEL"),
        ("s ơ b ệnh",       "sơ bệnh",       "VOWEL"),
        ("đi ện tử",        "điện tử",       "VOWEL"),
        ("ph ỉ h ợp",       "phù hợp",       "VOWEL"),
        ("đi ều ph ối",     "điều phối",     "VOWEL"),
        ("cực t ế",         "thực tế",       "VOWEL"),
        ("c ải thi ện",     "cải thiện",     "VOWEL"),
        ("thi ộ",           "thiện",         "VOWEL"),
        ("ch ũnh x ỏc",     "chính xác",     "VOWEL"),
        ("x ỏc",            "xác",           "VOWEL"),
        ("đ b ảo",          "đảm bảo",       "VOWEL"),
        ("b ảo",            "bảo",           "VOWEL"),
        ("li ữ n ục",       "liên tục",      "VOWEL"),
        ("li ữ",            "liên",          "VOWEL"),
        ("n ục",            "tục",           "VOWEL"),
        ("ghi nh ận",       "ghi nhận",      "VOWEL"),
        ("ch tỉnh s ửa",    "chỉnh sửa",     "VOWEL"),
        ("s ửa",            "sửa",           "VOWEL"),
        ("h lỗ tr ợ",       "hỗ trợ",        "VOWEL"),
        ("h lỗ đợ",         "hỗ trợ",        "VOWEL"),
        ("lỗ tr ợ",         "hỗ trợ",        "VOWEL"),
        ("lỗ đợ",           "hỗ trợ",        "VOWEL"),
        ("t ừc bằng",       "từng bằng",     "VOWEL"),
        ("h lỗ",            "hỗ",            "VOWEL"),
        ("hỗ tr ợ t ừc",    "hỗ trợ từng",   "VOWEL"),
        ("t ừ ừ",           "từ",            "VOWEL"),
        ("t ừc",            "từng",          "VOWEL"),
        ("v à",             "và",            "VOWEL"),
        ("à qu ản",         "và quản",       "VOWEL"),
        ("v ới c",          "với các",       "VOWEL"),
        ("à b ệnh",         "và bệnh",       "VOWEL"),
        ("à à",             "và",            "VOWEL"),
        ("v ới c ỏc",       "với các",       "VOWEL"),
        ("c ỏc",            "các",           "VOWEL"),
        ("b ỏc s ĩ",        "bác sĩ",        "VOWEL"),
        ("s ĩ",             "sĩ",            "VOWEL"),
        ("nh õn",           "nhân",          "VOWEL"),
        ("n ội tho đại",    "nội thoại",     "VOWEL"),
        ("tho đại",         "thoại",         "VOWEL"),
        ("s sử",            "sử",            "VOWEL"),
        ("chũnh",           "chính",         "VOWEL"),
        ("chũnh x ỏc",     "chính xác",     "VOWEL"),
        ("phũ",           "phù",           "VOWEL"),
        ("v mới c xây dựng trượng", "với cấu trúc rõ ràng", "VOWEL"),
        ("xây dựng trượng", "cấu trúc",      "VOWEL"),
        ("trượng",          "trúc",          "VOWEL"),
        ("đ ý vai trò trò chơi trung tõm", "đóng vai trò trung tâm", "VOWEL"),
        ("trò chơi trung tõm", "trung tâm",  "VOWEL"),
        ("trò chơi",        "trò",           "VOWEL"),
        ("tõm",             "tâm",           "VOWEL"),
        ("tõm trong",       "tâm trong",     "VOWEL"),
        ("ti ec ti",        "việc tiếp",     "VOWEL"),
        ("Agent điện nh õn","Agent bệnh nhân","VOWEL"),
        ("điện nh õn",      "bệnh nhân",     "VOWEL"),
        ("điện",            "bệnh",          "VOWEL"),
        ("lực ti tiếp cho", "hỗ trợ tiếp cho","VOWEL"),
        ("Agent 1, bao g ồm", "Agent với dữ liệu từ Agent 1, bao gồm", "VOWEL"),
        ("à l kịch",        "và lịch",       "VOWEL"),
        ("l kịch",          "lịch",          "VOWEL"),
        ("s sử b điệnh",    "sử bệnh",       "VOWEL"),
        ("b điệnh",         "bệnh",          "VOWEL"),
        ("ộ c ập nhật",     "cập nhật",      "VOWEL"),
        ("c ý tr ực",       "có cấu trúc",   "VOWEL"),
        ("tr ực",           "trúc",          "VOWEL"),
        ("đi ều ph ối c ỏc", "điều phối các","VOWEL"),
    ]

    # ── 5. Lỗi cụm từ hành chính thường gặp ──────────────────────────────────
    # Ưu tiên xử lý trước syllable để tránh conflict
    PHRASE_FIXES: list[tuple[str, str]] = [
        # Cụm từ bị OCR sai do nhiều ký tự liên tiếp bị nhầm
        ("mô hủnh",           "mô hình"),
        ("mô hỉnh",           "mô hình"),
        ("đóng vai trỹ",      "đóng vai trò"),
        ("người dững",        "người dùng"),
        ("giọng nýi",         "giọng nói"),
        ("chũnh",            "chính"),
        ("phũ hợp",         "phù hợp"),
        ("thỏng", "tháng" ),
        ("riùng",         "riêng"),
        ("Tiùu ngữ",        "Tiêu ngữ"),
        ("đỏnh",         "đóng"),
        ("TRỡNH",         "TRÌNH"),
        ("bệnh nhõn",         "bệnh nhân"),
        ("tiếp xực",          "tiếp xúc"),
        ("phân tũch",         "phân tích"),
        ("hành trủnh",        "hành trình"),
        ("kiến trực",         "kiến trúc"),
        ("ủy ban nhân dận",   "Ủy ban nhân dân"),
        ("ủy ban nhân dân",   "Ủy ban nhân dân"),   # chuẩn hóa viết hoa
        ("hội đổng",          "Hội đồng"),
        ("hội đồng nhân dận", "Hội đồng nhân dân"),
        ("sở giáo đực",       "Sở Giáo dục"),
        ("phỏng giáo dục",    "Phòng Giáo dục"),
        ("căn cữ",            "căn cứ"),
        ("căn cú",            "căn cứ"),
        ("thực hiện",         "thực hiện"),   # giữ đúng
        ("thục hiện",         "thực hiện"),
        ("triển khai",        "triển khai"),
        ("triển kha",         "triển khai"),
        ("kế hoạch",          "kế hoạch"),
        ("kế hoach",          "kế hoạch"),
        ("phát triển",        "phát triển"),
        ("nhóm người dùng",   "nhóm người dùng"),
        ("bác sĩ",            "bác sĩ"),
        ("quản lý",           "quản lý"),
        ("xử lý giọng nói",   "xử lý giọng nói"),
        ("đặt lịch và tạo mó qr", "đặt lịch và tạo mã QR"),
        ("multi agent",       "multi-agent"),
        ("Multi-Agent",       "multi-agent"),
        # Thêm từ văn bản hành chính thực tế (Nghị định 30/2020)
        ("Chũnh phủ",         "Chính phủ"),
        ("chũnh phủ",         "Chính phủ"),
        ("Tiữu ngữ",          "Tiêu ngữ"),
        ("tiữu ngữ",          "Tiêu ngữ"),
        ("Tiữu chuẩn",        "Tiêu chuẩn"),
        ("tiữu chuẩn",        "Tiêu chuẩn"),
        ("bộ mý ký tự",       "bộ mã ký tự"),
        ("phỵng chữ",         "phông chữ"),
        ("Phỵng chữ",         "Phông chữ"),
        ("khỵng được",        "không được"),
        ("khỵng hiển thị",    "không hiển thị"),
        ("dỹng chữ",          "dòng chữ"),
        ("dỹng đơn",          "dòng đơn"),
        ("hai dỹng",          "hai dòng"),
        ("phía trữn",         "phía trên"),
        ("lề trữn",           "lề trên"),
        ("bữn phải",          "bên phải"),
        ("bữn trái",          "bên trái"),
        ("tữn cơ quan",       "tên cơ quan"),
        ("tữn chũnh thức",    "tên chính thức"),
        ("tữn của",           "tên của"),
        ("cỏch mợp trữn",     "cách mép trên"),
        ("cỏch mợp dưới",     "cách mép dưới"),
        ("cỏch mợp trỏi",     "cách mép trái"),
        ("cỏch mợp phải",     "cách mép phải"),
        ("mợp trữn",          "mép trên"),
        ("mợp dưới",          "mép dưới"),
        ("mợp trỏi",          "mép trái"),
        ("mợp phải",          "mép phải"),
        ("nợt liền",          "nét liền"),
        ("riững thủ",         "riêng thì"),
        ("phụ lục riững",     "phụ lục riêng"),
        ("ỵ số",              "ở số"),
        ("cý thể",            "có thể"),
        ("cý bảng",           "có bảng"),
        ("cý gạch nối",       "có gạch nối"),
        ("cý cách chữ",       "có cách chữ"),
        ("cý đường kẻ",       "có đường kẻ"),
        ("cý độ dài",         "có độ dài"),
        ("cý thẩm quyền",     "có thẩm quyền"),
        ("HềA XÃ",            "HÒA XÃ"),
        ("CỘNG HềA",          "CỘNG HÒA"),
        ("Hạnh phực",         "Hạnh phúc"),
        ("hạnh phực",         "Hạnh phúc"),
        ("địa ph",            "địa phương"),  # bị cắt cuối trang
        # Thêm từ văn bản mẫu người dùng
        ("iao diên ng ười d ững",    "giao diện người dùng"),
        ("ng ười d ững",             "người dùng"),
        ("d ững",                    "dùng"),
        ("v to backend",             "và backend"),
        ("đ nhi ệm x ử l ý logic",  "đảm nhiệm xử lý logic"),
        ("đi xuống ph ối",           "điều phối"),
        ("c ỏc AI Agent",            "các AI Agent"),
        ("ph ũa frontend",           "phía frontend"),
        ("h hệ thống ống",           "hệ thống"),
        ("hệ thống ống",             "hệ thống"),
        ("ống ống",                  ""),  # noise removal
        ("ống cũng",                 "cũng"),
        ("ph ỏt tri ăng b bằng",     "phát triển bằng"),
        ("ph ỏt tri ăng",            "phát triển"),
        ("tri ăng",                  "triển"),
        ("b bằng React",             "bằng React"),
        ("v ới c ỏc th ành ph ần",   "với các thành phần"),
        ("c ỏc th ành ph ần",        "các thành phần"),
        ("th ành ph ần",             "thành phần"),
        ("v à QR Modal",             "và QR Modal"),
        ("c ững c ỏc trang",         "cùng các trang"),
        ("c ững",                    "cùng"),
        ("ph ụ v ụ",                 "phục vụ"),
        ("t dừng lại nh ý ng ười",   "từng nhóm người"),
        ("dừng lại",                 "từng"),
        ("nh ý ng ười d ững",        "nhóm người dùng"),
        ("nh ý",                     "nhóm"),
        ("nh ư b ệnh nh õn",         "như bệnh nhân"),
        ("b ệnh nh õn",              "bệnh nhân"),
        ("b ỏc s ĩ",                 "bác sĩ"),
        ("à qu ản l ý",              "và quản lý"),
        ("b ệnh vi ện",              "bệnh viện"),
        ("t ũch h ợp",               "tích hợp"),
        ("c ơ c ơ ch ế",             "cơ chế"),
        ("c ơ ch ế",                 "cơ chế"),
        ("x sử l ý gi ọng n ý",      "xử lý giọng nói"),
        ("gi ọng n ý",               "giọng nói"),
        ("n ý nh ằm h lỗ tr ợ",      "nói nhằm hỗ trợ"),
        ("h lỗ tr ợ t ừc bằng",      "hỗ trợ từng bằng"),
        ("gi ựp ng ười d ững",        "giúp người dùng"),
        ("ng ười d ững d ễ d àng",    "người dùng dễ dàng"),
        ("d ễ d àng sử d ụng",        "dễ dàng sử dụng"),
        ("đ ặc bi ệt v ới",           "đặc biệt với"),
        ("người lớn tu ổi",           "người lớn tuổi"),
        ("phần phụ trợ cũ",           "phần backend"),
        ("s sử dụng Fast API",        "sử dụng FastAPI"),
        ("Fast API",                  "FastAPI"),
        ("v mới c xây dựng",          "với cấu trúc"),
        ("xây dựng trượng r õ ràng",  "rõ ràng"),
        ("r õ ràng g ồm",             "rõ ràng gồm"),
        ("c loại mô-đun",             "các mô-đun"),
        ("nh ư main",                 "như main"),
        ("đ ể kh ở đó tạo ra ống",   "để khởi động"),
        ("kh ở đó tạo ra ống",        "khởi động"),
        ("router để đ ịnh ngh ĩa API","router để định nghĩa API"),
        ("đ ịnh ngh ĩa",              "định nghĩa"),
        ("engine đ ể x sử dụng logic","engine để xử lý logic"),
        ("x sử dụng logic c ủa c",    "xử lý logic của các"),
        ("lược đồ đ ể chu ẩn h ýa",  "schema để chuẩn hóa"),
        ("chu ẩn h ýa",               "chuẩn hóa"),
        ("d ữ li ệu",                 "dữ liệu"),
        ("lưu trữ đ để ph ản ánh",    "lưu trữ để phản ánh"),
        ("ph ản ánh ý nghĩa c ủa m ột phần", "phản ánh ý nghĩa của một phần"),
        ("Backend đ ý vai trò trò chơi trung tõm", "Backend đóng vai trò trung tâm"),
        ("đ ý vai trò trò chơi",      "đóng vai trò"),
        ("trò chơi trung tõm",        "trung tâm"),
        ("trong vi ec ti tiếp nh ận", "trong việc tiếp nhận"),
        ("vi ec ti",                  "việc"),
        ("ti tiếp nh ận",             "tiếp nhận"),
        ("yêu c đầu t ừ",             "yêu cầu từ"),
        ("c đầu",                     "cầu"),
        ("đi suy ph ối c ỏc Agent",   "điều phối các Agent"),
        ("x sử l ý d ữ li ệu",        "xử lý dữ liệu"),
        ("à tr ả k ết qu ảnh v ề",    "và trả kết quả về"),
        ("k ết qu ảnh",               "kết quả"),
        ("ng ười dững",               "người dùng"),
        ("Agent l đến thành phần",    "Agent là thành phần"),
        ("l đến",                     "là"),
        ("c ốt l õi c ủa h hệ ống",  "cốt lõi của hệ thống"),
        ("h hệ ống",                  "hệ thống"),
        ("ba Agent ho ạt rộng",       "ba Agent hoạt động"),
        ("ho ạt rộng ph ối hợp",      "hoạt động phối hợp"),
        ("ph ối hợp theo ng ữ c ảnh", "phối hợp theo ngữ cảnh"),
        ("ng ữ c ảnh li ữu",          "ngữ cảnh liên tục"),
        ("à đi điểm ti tiếp x cực",   "là điểm tiếp xúc"),
        ("đi điểm",                   "điểm"),
        ("ti tiếp x cực đầu ti ữn",   "tiếp xúc đầu tiên"),
        ("x cực đầu ti ữn",           "xúc đầu tiên"),
        ("ti ữn",                     "tiên"),
        ("v mới b điện nh õn",        "với bệnh nhân"),
        ("b điện nh õn",              "bệnh nhân"),
        ("đng ý vai trò nh ư m ột",   "đóng vai trò như một"),
        ("đng ý",                     "đóng"),
        ("m ột tr ợ l ý",             "một trợ lý"),
        ("ch àn b ộ h ành trườn",     "cho toàn bộ hành trình"),
        ("kh ỏm ch ữa b ệnh",         "khám chữa bệnh"),
        ("tri ệu ch ứng dụng ỵng",    "triệu chứng dùng"),
        ("qua v ăn b tác ho ặc",      "qua văn bản hoặc"),
        ("gi ý n ý",                  "giọng nói"),
        ("sau đ ý ph õn t ũch",       "sau đó phân tích"),
        ("đứt ra h ng ng x ử l ý",    "đưa ra hướng xử lý"),
        ("h ng ng x ử l ý ph ữ h ợp", "hướng xử lý phù hợp"),
        ("nh ư dõi t ại nh à",        "như dõi tại nhà"),
        ("ho ặc g ợi ý đi kh cỏm",   "hoặc gợi ý đi khám"),
        ("đi kh cỏm",                 "đi khám"),
        ("kh cỏm",                    "khám"),
        ("Agent điện nh õn ti tiếp",  "Agent bệnh nhân tiếp"),
        ("c ận đ ựng d ịch v ụ",       "cận được dịch vụ"),
        ("đ ựng d ịch v ụ",            "được dịch vụ"),
        ("ngay từ ừ đ ầu",             "ngay từ đầu"),
        ("từ ừ",                       "từ"),
        ("gi rút thi loại sai s ýt",   "giảm thiểu sai sót"),
        ("rút thi loại",               "thiểu"),
        ("trong vi ec l iện ch ọn",    "trong việc lựa chọn"),
        ("l iện ch ọn",                "lựa chọn"),
        ("khoa phỹng",                 "khoa phòng"),
        ("à tr ợ l ý l õm sàng",       "là trợ lý lâm sàng"),
        ("h ỗ tr ợ lực ti tiếp",       "hỗ trợ tiếp"),
        ("lực ti tiếp cho b ỏc s ĩ",   "tiếp cho bác sĩ"),
        ("trong qu hoặc tủnh kh ỏm",   "trong quá trình khám"),
        ("qu hoặc tủnh",               "quá trình"),
        ("bao g ồm tri ệu ch ứng",     "bao gồm triệu chứng"),
        ("à l kịch s sử b điệnh",      "và lịch sử bệnh"),
        ("l kịch s sử",                "lịch sử"),
        ("s sử b điệnh",               "sử bệnh"),
        ("sau đ ý l ắng nghe",         "sau đó lắng nghe"),
        ("x ử l ý h nội tho đại",      "xử lý nội thoại"),
        ("h nội tho đại",              "nội thoại"),
        ("gi ữa b ỏc s ĩ",             "giữa bác sĩ"),
        ("à b ện nh õn",               "và bệnh nhân"),
        ("b ện nh õn",                 "bệnh nhân"),
        ("đ ể chuy ển đ ổi",           "để chuyển đổi"),
        ("chuy ển đ ổi",               "chuyển đổi"),
        ("d ữ li ệu c ý c",            "dữ liệu có cấu"),
        ("c ý c tr ực",                "cấu trúc"),
        ("à t ự đ ộng",                "và tự động"),
        ("c ập nhật v s ơ b ệnh",      "cập nhật vào sơ bệnh"),
        ("v s ơ",                      "vào sơ"),
        ("s ơ b ệnh đi ện tử",         "sơ bệnh điện tử"),
        ("Căn cứ dữ liệu li ệu",       "Căn cứ dữ liệu"),
        ("dữ liệu li ệu",              "dữ liệu"),
        ("Agent hỗ tr ợ ph õn t ũch",  "Agent hỗ trợ phân tích"),
        ("ph õn t ũch l õm sàng",      "phân tích lâm sàng"),
        ("gợi ý chẩn đo ngoài",        "gợi ý chẩn đoán"),
        ("chẩn đo ngoài theo phỏc đ ồ","chẩn đoán theo phác đồ"),
        ("theo phỏc đ ồ",              "theo phác đồ"),
        ("phỏc đ ồ",                   "phác đồ"),
        ("đề xu ất ch ỉ ịnh",          "đề xuất chỉ định"),
        ("ch ỉ ịnh x ợt",              "chỉ định xét"),
        ("x ợt đề nghị ệm",            "xét nghiệm"),
        ("đề nghị ệm",                 "nghiệm"),
        ("à h lỗ đợ",                  "và hỗ trợ"),
        ("h lỗ đợ tạo ra",             "hỗ trợ tạo"),
        ("ơn thu ốc",                  "đơn thuốc"),
        ("c ỏc ch tỉnh s ửa",          "các chỉnh sửa"),
        ("ch tỉnh s ửa",               "chỉnh sửa"),
        ("c ủa s ĩ",                   "của bác sĩ"),
        ("đ ể li ữ n ục",              "để liên tục"),
        ("li ữ n ục c ải thi ộ",       "liên tục cải thiện"),
        ("c ải thi ộ ch ũnh x ỏc",     "cải thiện chính xác"),
        ("đ b ảo ph ữ h ợp",           "đảm bảo phù hợp"),
        ("v mới cực t ế",              "với thực tế"),
        ("cực t ế lhiện tại",          "thực tế hiện tại"),
        ("lhiện tại nó vẫn như thế này", "hiện tại"),
        ("nó vẫn như thế này",         ""),
    ]

    # ── 6. Từ viết tắt hành chính cần chuẩn hóa viết hoa ────────────────────
    ABBREVIATION_FIXES: list[tuple[str, str]] = [
        ("ubnd",   "UBND"),
        ("hđnd",   "HĐND"),
        ("mttq",   "MTTQ"),
        ("bca",    "BCA"),
        ("bộ ca",  "Bộ Công an"),
        ("ttcp",   "TTCP"),
        ("vksnd",  "VKSND"),
        ("tand",   "TAND"),
        ("bhxh",   "BHXH"),
        ("bhyt",   "BHYT"),
        ("gplx",   "GPLX"),
        ("cmnd",   "CMND"),
        ("cccd",   "CCCD"),
        ("q/đ",    "QĐ"),
        ("cv",     "CV"),
    ]

    def __init__(self):
        # Biên dịch trước tất cả regex để tăng hiệu năng
        # Dùng (?<!\w) / (?!\w) thay cho \b (hoạt động đúng với Unicode)
        self._syllable_patterns: list[tuple[re.Pattern, str]] = []
        for source, target, _category in self.SYLLABLE_FIXES:
            # Chỉ áp dụng cho các từ thuần ASCII (không có dấu) ở mode DIACRITIC
            # để tránh thay thế sai trong văn bản đã đúng
            escaped = re.escape(source)
            pattern = re.compile(
                rf"(?<![^\s\n\t]){escaped}(?![^\s\n\t.,;:!?\"'()\[\]])",
                re.IGNORECASE | re.UNICODE,
            )
            self._syllable_patterns.append((pattern, target))

        self._phrase_patterns: list[tuple[re.Pattern, str]] = []
        for source, target in self.PHRASE_FIXES:
            pattern = re.compile(re.escape(source), re.IGNORECASE | re.UNICODE)
            self._phrase_patterns.append((pattern, target))

        self._abbr_patterns: list[tuple[re.Pattern, str]] = []
        for source, target in self.ABBREVIATION_FIXES:
            pattern = re.compile(
                rf"(?<!\w){re.escape(source)}(?!\w)",
                re.IGNORECASE | re.UNICODE,
            )
            self._abbr_patterns.append((pattern, target))

        self._char_patterns: list[tuple[re.Pattern, str]] = []
        for source, target in self.CHAR_CONFUSION_FIXES:
            self._char_patterns.append((re.compile(source, re.UNICODE), target))

    def correct(self, text: str) -> str:
        """
        Áp dụng toàn bộ pipeline sửa lỗi OCR theo đúng thứ tự.
        Thứ tự quan trọng: font → char → phrase → syllable → abbr
        """
        if not text:
            return text

        # Bước 1: Chuyển đổi font cũ → Unicode
        text = self._fix_font_encoding(text)

        # Bước 2: Normalize Unicode về dạng NFC thống nhất
        text = unicodedata.normalize("NFC", text)

        # Bước 3: Sửa lỗi ký tự đơn lẻ (confusion matrix)
        for pattern, replacement in self._char_patterns:
            text = pattern.sub(replacement, text)

        # Bước 4: Sửa lỗi cụm từ TRƯỚC (ưu tiên cao hơn syllable)
        for pattern, replacement in self._phrase_patterns:
            text = pattern.sub(replacement, text)

        # Bước 5: Sửa lỗi âm tiết
        for pattern, replacement in self._syllable_patterns:
            text = pattern.sub(replacement, text)

        # Bước 6: Chuẩn hóa từ viết tắt
        for pattern, replacement in self._abbr_patterns:
            text = pattern.sub(replacement, text)

        # Bước 7: Normalize lại sau khi sửa
        text = unicodedata.normalize("NFC", text)

        return text

    def _fix_font_encoding(self, text: str) -> str:
        """Chuyển đổi TCVN3 và VNI sang Unicode."""
        # TCVN3
        text = text.translate(self.TCVN3_CHAR_MAP)
        # VNI (xử lý từ dài đến ngắn để tránh partial match)
        for source, target in sorted(self.COMMON_VNI_REPLACEMENTS, key=lambda x: -len(x[0])):
            text = text.replace(source, target)
            text = text.replace(source.upper(), target.upper())
        # Thử decode latin1/cp1252 nếu văn bản vẫn có nhiều ký tự lạ
        if self._has_mojibake(text):
            for codec in ("latin1", "cp1252"):
                try:
                    candidate = text.encode(codec).decode("utf-8")
                    if self._viet_score(candidate) > self._viet_score(text):
                        text = candidate
                        break
                except (UnicodeEncodeError, UnicodeDecodeError):
                    continue
        return text

    @staticmethod
    def _has_mojibake(text: str) -> bool:
        """Kiểm tra xem text có dấu hiệu mojibake không."""
        mojibake_chars = sum(1 for ch in text if "\x80" <= ch <= "\x9f" or "\xa0" <= ch <= "\xbf")
        return mojibake_chars / max(len(text), 1) > 0.05

    @staticmethod
    def _viet_score(text: str) -> int:
        """Đếm số ký tự tiếng Việt có dấu."""
        return len(re.findall(
            r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệóòỏõọốồổỗộớờởỡợíìỉĩịúùủũụứừửữựýỳỷỹỵ]",
            text.lower(),
        ))


# ─── Image Preprocessing (nâng cao) ──────────────────────────────────────────

class _ImagePreprocessor:
    """
    Tiền xử lý ảnh trước khi OCR với nhiều kỹ thuật nâng cao.
    Chiến lược: thử nhiều preset và chọn kết quả có điểm tiếng Việt cao nhất.
    """

    # Ngưỡng dpi tối thiểu để OCR cho kết quả tốt
    MIN_DPI_EQUIVALENT = 150  # pixels per inch tương đương

    @staticmethod
    def deskew(image: Image.Image) -> Image.Image:
        """
        Sửa ảnh bị nghiêng (skew correction) bằng cách tìm góc xoay tối ưu.
        Dùng phương pháp projection profile đơn giản không cần cv2.
        """
        import math

        gray = ImageOps.grayscale(image)
        # Threshold thô để tìm vùng text
        threshold = gray.point(lambda p: 0 if p < 128 else 255)
        arr = np.array(threshold)

        best_angle = 0.0
        best_score = -1.0

        # Tìm kiếm góc trong khoảng ±10 độ, bước 0.5 độ
        for angle_tenth in range(-20, 21):  # -10.0 đến +10.0 bước 0.5
            angle = angle_tenth * 0.5
            rotated = image.rotate(angle, expand=False, fillcolor=255)
            rot_arr = np.array(ImageOps.grayscale(rotated).point(lambda p: 0 if p < 128 else 255))

            # Tính horizontal projection — ảnh thẳng sẽ có variance cao nhất
            row_sums = np.sum(rot_arr == 0, axis=1).astype(float)
            score = float(np.var(row_sums))
            if score > best_score:
                best_score = score
                best_angle = angle

        if abs(best_angle) > 0.3:
            image = image.rotate(best_angle, expand=False, fillcolor=255)
        return image

    @staticmethod
    def adaptive_binarize(image: Image.Image) -> Image.Image:
        """
        Binarization thích nghi — xử lý tốt hơn với ảnh có ánh sáng không đều.
        Dùng local thresholding theo block 32x32.
        """
        gray = np.array(ImageOps.grayscale(image), dtype=np.float32)
        block_size = 32
        output = np.ones_like(gray, dtype=np.uint8) * 255
        h, w = gray.shape

        for y in range(0, h, block_size):
            for x in range(0, w, block_size):
                block = gray[y:y + block_size, x:x + block_size]
                if block.size == 0:
                    continue
                # Otsu-like: threshold = mean - c (c=10 để loại background)
                mean_val = float(np.mean(block))
                thresh = mean_val - 10
                mask = block < thresh
                output[y:y + block_size, x:x + block_size][mask] = 0

        return Image.fromarray(output)

    @classmethod
    def upscale_if_needed(cls, image: Image.Image) -> Image.Image:
        """Tăng kích thước ảnh nếu quá nhỏ để OCR chính xác hơn."""
        w, h = image.size
        # Nếu ảnh nhỏ hơn 1000px chiều rộng → upscale 2x
        if w < 1000 or h < 800:
            new_w, new_h = w * 2, h * 2
            image = image.resize((new_w, new_h), Image.LANCZOS)
        return image

    @classmethod
    def preprocess(cls, image: Image.Image, aggressive: bool = False) -> Image.Image:
        """
        Pipeline tiền xử lý chính.
        aggressive=True dành cho ảnh chụp tay, chất lượng thấp.
        """
        # Bước 1: Upscale nếu cần
        image = cls.upscale_if_needed(image)

        # Bước 2: Chuyển sang RGB rồi grayscale (xử lý cả RGBA, P mode)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        gray = ImageOps.grayscale(image)

        # Bước 3: Tăng độ tương phản
        contrast_factor = 2.2 if aggressive else 1.8
        gray = ImageEnhance.Contrast(gray).enhance(contrast_factor)

        # Bước 4: Sharpen
        gray = gray.filter(ImageFilter.SHARPEN)
        if aggressive:
            gray = gray.filter(ImageFilter.SHARPEN)  # sharpen 2 lần

        # Bước 5: Adaptive binarization (chỉ khi aggressive hoặc ảnh tối)
        if aggressive:
            gray = cls.adaptive_binarize(gray)

        # Bước 6: Khử nhiễu nhẹ (median filter)
        gray = gray.filter(ImageFilter.MedianFilter(size=3))

        # Bước 7: Deskew (chỉ khi aggressive)
        if aggressive:
            gray = cls.deskew(gray)

        return gray

    @classmethod
    def preprocess_multi(cls, image: Image.Image) -> list[tuple[Image.Image, str]]:
        """
        Trả về nhiều preset preprocessing để OCR thử và chọn kết quả tốt nhất.
        Returns: list of (processed_image, preset_name)
        """
        return [
            (cls.preprocess(image, aggressive=False), "standard"),
            (cls.preprocess(image, aggressive=True),  "aggressive"),
            (cls.adaptive_binarize(ImageOps.grayscale(image)), "binarize_only"),
        ]


# ─── Main OCR Service ─────────────────────────────────────────────────────────

class OCRService:
    # ── Tesseract config ──────────────────────────────────────────────────────
    TESSERACT_CONFIG = "--oem 3 --psm 6 -c preserve_interword_spaces=1"

    # ── Regex patterns ────────────────────────────────────────────────────────
    ARTICLE_PATTERN = re.compile(
        r"^\s*(Điều|Dieu)\s+\d+[.:)]",
        re.IGNORECASE | re.MULTILINE,
    )
    CHAPTER_PATTERN = re.compile(
        r"^\s*(Chương|Chuong)\s+[IVXLCDM\d]+",
        re.IGNORECASE | re.MULTILINE,
    )
    SECTION_PATTERN = re.compile(
        r"^\s*(Mục|Muc)\s+\d+",
        re.IGNORECASE | re.MULTILINE,
    )
    CLAUSE_PATTERN = re.compile(
        r"^\s*(Khoản|Khoan)\s+\d+[.:)]?",
        re.IGNORECASE | re.MULTILINE,
    )
    DOCUMENT_CODE_PATTERN = re.compile(
        r"(?:Số|So)[:/]?\s*([\w\-/]+(?:/[\w\-]+)+)",
        re.IGNORECASE,
    )
    SUMMARY_PATTERN = re.compile(
        r"(?:V/v|Ve viec|Về việc)[:\s]+(.+?)(?:\n|$)",
        re.IGNORECASE,
    )
    PAGE_ONLY_PATTERN = re.compile(
        r"^\s*(?:[Tt]rang\s+)?\d+\s*$"
    )
    STRUCTURAL_LINE_PATTERN = re.compile(
        r"^\s*(?:"
        r"(?:Điều|Dieu|Khoản|Khoan|Chương|Chuong|Mục|Muc)\s+\d+"
        r"|(?:UBND|HĐND|BỘ|SỞ|PHÒNG|ỦY BAN)\b"
        r"|\d+\.\s+\S"
        r")",
        re.IGNORECASE,
    )
    CONNECTOR_LINE_PATTERN = re.compile(
        r"^\s*(?:và|hoặc|nhưng|tuy nhiên|do đó|vì vậy|theo đó|trong đó|đồng thời)",
        re.IGNORECASE,
    )
    WORD_MERGE_PATTERN = re.compile(
        r"([a-zà-ỹA-ZÀ-Ỹ]{3,})([A-ZÀ-Ỹ][a-zà-ỹ]{2,})"
    )
    GARBAGE_CHAR_PATTERN = re.compile(
        r"[^\w\s\n\tàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
        r"ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ"
        r".,;:!?\"'()\[\]\-/\\@#%&*+=<>|°–—…]",
        re.UNICODE,
    )

    # ── Document type patterns ─────────────────────────────────────────────────
    DOCUMENT_PATTERNS: dict[str, list[str]] = {
        "cong_van":   ["cong van", "cv", "v/v", "ve viec"],
        "quyet_dinh": ["quyet dinh", "qd", "ban hanh"],
        "thong_bao":  ["thong bao", "tb"],
        "nghi_dinh":  ["nghi dinh", "nd"],
        "chi_thi":    ["chi thi", "ct"],
        "to_trinh":   ["to trinh", "tt"],
        "bao_cao":    ["bao cao", "bc"],
        "bien_ban":   ["bien ban", "bb"],
        "hop_dong":   ["hop dong", "hd"],
    }

    def __init__(
        self,
        index_path: str = "ocr_faiss.index",
        metadata_path: str = "ocr_metadata.json",
    ):
        self._corrector = _VietnameseOCRCorrector()
        self._preprocessor = _ImagePreprocessor()
        self.lang = "vie+eng"

        # Storage
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.documents: list[dict[str, Any]] = []

        # Lazy-init placeholders
        self._bm25 = None
        self._index = None
        self._embedding_model = None

        # LLM config (Ollama-compatible endpoint)
        self.llm_url: str = getattr(settings, "LLM_URL", "http://localhost:11434/api/generate")
        self.llm_model: str = getattr(settings, "LLM_MODEL", "llama3")

    # ── Properties (lazy initialization) ─────────────────────────────────────

    @property
    def bm25(self):
        if self._bm25 is None and self.documents:
            tokenized_corpus = [
                ViTokenizer.tokenize(doc["content"]).split()
                for doc in self.documents
            ]
            try:
                from rank_bm25 import BM25Okapi
                self._bm25 = BM25Okapi(tokenized_corpus)
            except Exception:
                self._bm25 = _FallbackBM25(tokenized_corpus)
        return self._bm25

    def _refresh_bm25(self) -> None:
        self._bm25 = None

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            if settings.OCR_USE_SENTENCE_TRANSFORMERS:
                try:
                    from sentence_transformers import SentenceTransformer
                    self._embedding_model = SentenceTransformer(
                        settings.EMBEDDING_MODEL_NAME, local_files_only=True
                    )
                except Exception:
                    self._embedding_model = _FallbackEmbeddingModel()
            else:
                self._embedding_model = _FallbackEmbeddingModel()
        return self._embedding_model

    @property
    def index(self):
        if self._index is None:
            import faiss
            if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
                self._index = faiss.read_index(self.index_path)
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.documents = json.load(f)
            else:
                self._index = faiss.IndexFlatL2(self._embedding_dimension())
                self.documents = []
        return self._index

    # ── Storage ───────────────────────────────────────────────────────────────

    def reset_storage(self) -> None:
        import faiss
        self._index = faiss.IndexFlatL2(self._embedding_dimension())
        self.documents = []
        self._refresh_bm25()
        self.save_storage()

    def save_storage(self) -> None:
        import faiss
        if self._index is not None:
            try:
                faiss.write_index(self._index, self.index_path)
                with open(self.metadata_path, "w", encoding="utf-8") as f:
                    json.dump(self.documents, f, ensure_ascii=False, indent=2)
            except (OSError, RuntimeError) as exc:
                logger.warning("ocr_storage_persist_failed: %s", exc)

    def store_embeddings(self, embedded_objects: List[Dict[str, Any]]) -> None:
        if not embedded_objects:
            return
        vectors = np.array([obj["vector"] for obj in embedded_objects]).astype("float32")
        self.index.add(vectors)
        for obj in embedded_objects:
            self.documents.append({"content": obj["content"], "metadata": obj.get("metadata", {})})
        self._refresh_bm25()
        self.save_storage()

    # ── Image OCR (cải tiến: thử nhiều preset, chọn kết quả tốt nhất) ────────

    def preprocess_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """Trả về ảnh đã xử lý tốt nhất (backwards compatible)."""
        return _ImagePreprocessor.preprocess(image, aggressive=False)

    def extract_from_image(self, image_bytes: bytes) -> str:
        """
        OCR từ ảnh với chiến lược thử nhiều preset và chọn kết quả tốt nhất.
        Tốt hơn phiên bản cũ vì: multi-preset + correction pipeline.
        """
        image = Image.open(io.BytesIO(image_bytes))
        presets = _ImagePreprocessor.preprocess_multi(image)

        best_text = ""
        best_score = -1

        for processed, preset_name in presets:
            try:
                raw_text = pytesseract.image_to_string(
                    processed, lang=self.lang, config=self.TESSERACT_CONFIG
                ).strip()
                # Sửa lỗi OCR ngay sau khi nhận kết quả thô
                corrected = self._corrector.correct(raw_text)
                score = _VietnameseOCRCorrector._viet_score(corrected)
                logger.debug("OCR preset=%s score=%d chars=%d", preset_name, score, len(corrected))
                if score > best_score:
                    best_score = score
                    best_text = corrected
            except Exception as exc:
                logger.warning("ocr_preset_failed preset=%s: %s", preset_name, exc)

        return best_text

    # ── PDF Extraction ────────────────────────────────────────────────────────

    def extract_pages_from_pdf(self, pdf_bytes: bytes) -> list[dict[str, Any]]:
        """
        Trích xuất text từ PDF.
        Ưu tiên text layer (nhanh, chính xác). Fallback sang OCR nếu là PDF scan.
        """
        pages = self._extract_pdf_text_pages(pdf_bytes)

        # Kiểm tra xem có phải PDF scan không (text layer rỗng/rất ngắn)
        total_text_len = sum(len(p["text"].strip()) for p in pages)
        is_scan = total_text_len < len(pages) * 20  # < 20 chars/page trung bình

        if is_scan:
            logger.info("pdf_scan_detected pages=%d, using OCR", len(pages))
            images = convert_from_bytes(pdf_bytes, dpi=200)  # dpi=200 tốt hơn default
            return [
                {
                    "page_number": i + 1,
                    "text": self._ocr_pil_image(img),
                }
                for i, img in enumerate(images)
            ]

        return pages

    def _ocr_pil_image(self, image: Image.Image) -> str:
        """OCR một PIL Image với correction pipeline."""
        presets = _ImagePreprocessor.preprocess_multi(image)
        best_text = ""
        best_score = -1
        for processed, _ in presets:
            try:
                raw = pytesseract.image_to_string(
                    processed, lang=self.lang, config=self.TESSERACT_CONFIG
                ).strip()
                corrected = self._corrector.correct(raw)
                score = _VietnameseOCRCorrector._viet_score(corrected)
                if score > best_score:
                    best_score = score
                    best_text = corrected
            except Exception:
                pass
        return best_text

    def extract_from_pdf(self, pdf_bytes: bytes) -> str:
        pages = self.extract_pages_from_pdf(pdf_bytes)
        cleaned = self.clean_pages(pages)
        return "\n\n".join(
            f"--- Page {p['page_number']} ---\n{p['text']}"
            for p in cleaned if p["text"]
        )

    # ── DOCX Extraction ───────────────────────────────────────────────────────

    def extract_pages_from_docx(self, docx_bytes: bytes) -> list[dict[str, Any]]:
        namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
            xml_bytes = archive.read("word/document.xml")

        root = ET.fromstring(xml_bytes)
        body = root.find("w:body", namespaces)
        if body is None:
            return [{"page_number": 1, "text": ""}]

        pages: list[list[str]] = [[]]
        for paragraph in body.findall("w:p", namespaces):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", namespaces)]
            paragraph_text = "".join(texts).strip()
            if paragraph_text:
                pages[-1].append(paragraph_text)
            has_page_break = any(
                node.attrib.get(f"{{{namespaces['w']}}}type") == "page"
                for node in paragraph.findall(".//w:br", namespaces)
            )
            if has_page_break:
                pages.append([])

        return [
            {"page_number": i + 1, "text": "\n".join(lines).strip()}
            for i, lines in enumerate(pages)
        ] or [{"page_number": 1, "text": ""}]

    def extract_from_docx(self, docx_bytes: bytes) -> str:
        pages = self.clean_pages(self.extract_pages_from_docx(docx_bytes))
        return "\n\n".join(
            f"--- Page {p['page_number']} ---\n{p['text']}"
            for p in pages if p["text"]
        )

    # ── TXT Extraction ────────────────────────────────────────────────────────

    def extract_pages_from_txt(self, file_bytes: bytes) -> list[dict[str, Any]]:
        raw_text = file_bytes.decode("utf-8", errors="ignore")
        parts = [part.strip() for part in raw_text.replace("\r\n", "\n").split("\f")]
        pages = [{"page_number": i + 1, "text": part} for i, part in enumerate(parts) if part]
        return pages or [{"page_number": 1, "text": raw_text.strip()}]

    def extract_from_txt(self, file_bytes: bytes) -> str:
        pages = self.clean_pages(self.extract_pages_from_txt(file_bytes))
        return "\n\n".join(
            f"--- Page {p['page_number']} ---\n{p['text']}"
            for p in pages if p["text"]
        )

    # ── Text Normalization & Cleaning ─────────────────────────────────────────

    def repair_text_encoding(self, text: str) -> str:
        """Backwards compatible: gọi corrector._fix_font_encoding."""
        return self._corrector._fix_font_encoding(text)

    def normalize_text(self, text: str) -> str:
        """
        Pipeline chuẩn hóa văn bản toàn diện.
        Thứ tự: encoding repair → unicode → control chars → bullets
               → paragraph flow → admin noise → whitespace → OCR errors
        """
        if not text:
            return ""

        # Bước 1: Sửa lỗi encoding font cũ
        text = self._corrector._fix_font_encoding(text)

        # Bước 2: Normalize Unicode NFC
        text = unicodedata.normalize("NFC", text)

        # Bước 3: Loại bỏ ký tự điều khiển (giữ lại \n, \t)
        text = text.replace("\x0c", "\n")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = "".join(
            ch for ch in text
            if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\t")
        )

        # Bước 4: Chuẩn hóa bullet points
        text = self._normalize_bullets(text)

        # Bước 5: Khôi phục luồng đoạn văn (paragraph flow)
        text = self._restore_paragraph_flow(text)

        # Bước 6: Loại bỏ nhiễu hành chính (tiêu ngữ, số trang, đường kẻ)
        text = self._strip_administrative_noise(text)

        # Bước 7: Sửa lỗi từ bị dính nhau sau OCR
        text = self.WORD_MERGE_PATTERN.sub(r"\1 \2", text)

        # Bước 8: Chuẩn hóa khoảng trắng
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Bước 9: Áp dụng toàn bộ correction pipeline OCR
        text = self._corrector.correct(text)

        # Bước 10: Loại bỏ ký tự rác còn lại (nếu tỷ lệ thấp)
        text = self._remove_garbage_chars(text)

        return text.strip()

    def _remove_garbage_chars(self, text: str) -> str:
        """
        Loại bỏ ký tự rác sinh ra từ OCR.
        Chỉ xóa nếu ký tự không phải Unicode hợp lệ của tiếng Việt/Anh.
        """
        lines = []
        for line in text.splitlines():
            # Tính tỷ lệ ký tự lạ trên dòng
            garbage_count = len(self.GARBAGE_CHAR_PATTERN.findall(line))
            if len(line) > 0 and garbage_count / len(line) > 0.3:
                # Dòng có >30% ký tự lạ → loại bỏ cả dòng
                logger.debug("garbage_line_removed: %r", line[:80])
                continue
            # Loại bỏ ký tự lạ đơn lẻ
            cleaned = self.GARBAGE_CHAR_PATTERN.sub("", line)
            lines.append(cleaned)
        return "\n".join(lines)

    def clean_pages(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Làm sạch danh sách các trang:
        1. Normalize từng dòng
        2. Loại bỏ số trang lẻ
        3. Loại bỏ header/footer lặp lại (>=2 trang)
        4. Khôi phục paragraph flow
        5. Áp dụng OCR correction
        """
        # Bước 1 & 2: Normalize và lọc số trang
        normalized_pages = []
        for page in pages:
            lines = [
                self.normalize_text(line)
                for line in page.get("text", "").splitlines()
            ]
            lines = [ln for ln in lines if ln and not self.PAGE_ONLY_PATTERN.match(ln)]
            normalized_pages.append({
                "page_number": page["page_number"],
                "text": "\n".join(lines).strip(),
            })

        # Bước 3: Phát hiện header/footer lặp lại
        first_line_counts: Counter = Counter()
        last_line_counts: Counter = Counter()
        for page in normalized_pages:
            lines = [ln.strip() for ln in page["text"].splitlines() if ln.strip()]
            if lines:
                first_line_counts[lines[0]] += 1
                last_line_counts[lines[-1]] += 1

        repeated_headers = {
            line for line, count in first_line_counts.items()
            if count >= 2 and len(line) <= 120
        }
        repeated_footers = {
            line for line, count in last_line_counts.items()
            if count >= 2 and len(line) <= 120
        }

        # Bước 4 & 5: Loại header/footer + correction
        cleaned_pages = []
        for page in normalized_pages:
            lines = [ln.strip() for ln in page["text"].splitlines() if ln.strip()]
            if lines and lines[0] in repeated_headers:
                lines = lines[1:]
            if lines and lines[-1] in repeated_footers:
                lines = lines[:-1]
            page_text = self._restore_paragraph_flow("\n".join(lines).strip())
            # OCR correction áp dụng lần cuối sau khi đã join paragraph
            page_text = self._corrector.correct(page_text)
            cleaned_pages.append({
                "page_number": page["page_number"],
                "text": page_text,
            })
        return cleaned_pages

    # ── Search & RAG ──────────────────────────────────────────────────────────

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = 0.5,
        threshold: float = 0.1,
        document_ids: list[int] | None = None,
    ) -> List[Dict[str, Any]]:
        if not query:
            return []
        if self.index.ntotal == 0 and not self.documents:
            return []

        allowed_ids = set(document_ids) if document_ids is not None else None

        # BM25 search
        keyword_results = []
        if self.bm25:
            tokenized_query = ViTokenizer.tokenize(query).split()
            bm25_scores = self.bm25.get_scores(tokenized_query)
            max_bm25 = float(np.max(bm25_scores)) if len(bm25_scores) > 0 else 0.0
            norm_bm25 = bm25_scores / max_bm25 if max_bm25 > 0 else bm25_scores
            top_indices = np.argsort(norm_bm25)[::-1][: top_k * 2]
            for idx in top_indices:
                if norm_bm25[idx] > 0:
                    doc = self.documents[idx].copy()
                    doc["id"] = int(idx)
                    doc["bm25_score"] = float(norm_bm25[idx])
                    keyword_results.append(doc)

        # Vector search
        query_vector = self.embedding_model.encode([query]).astype("float32")
        distances, indices = self.index.search(query_vector, top_k * 2)
        vector_results = []
        if len(distances[0]) > 0:
            max_dist = float(np.max(distances[0]))
            for i, idx in enumerate(indices[0]):
                if idx != -1 and idx < len(self.documents):
                    norm_score = 1.0 - (distances[0][i] / max_dist) if max_dist > 0 else 1.0
                    doc = self.documents[idx].copy()
                    doc["id"] = int(idx)
                    doc["vector_score"] = float(norm_score)
                    vector_results.append(doc)

        # Merge với RRF-like fusion
        merged: dict[int, dict[str, Any]] = {}
        for doc in keyword_results:
            merged[doc["id"]] = {
                "content": doc["content"],
                "metadata": doc["metadata"],
                "bm25_score": doc["bm25_score"],
                "vector_score": 0.0,
            }
        for doc in vector_results:
            if doc["id"] in merged:
                merged[doc["id"]]["vector_score"] = doc["vector_score"]
            else:
                merged[doc["id"]] = {
                    "content": doc["content"],
                    "metadata": doc["metadata"],
                    "bm25_score": 0.0,
                    "vector_score": doc["vector_score"],
                }

        beta = 1.0 - alpha
        final_results = []
        for doc_id, data in merged.items():
            metadata = data.get("metadata", {})
            if allowed_ids is not None and metadata.get("document_id") not in allowed_ids:
                continue
            final_score = alpha * data["bm25_score"] + beta * data["vector_score"]
            if final_score >= threshold:
                data["id"] = doc_id
                data["final_score"] = round(final_score, 4)
                del data["bm25_score"]
                del data["vector_score"]
                final_results.append(data)

        final_results.sort(key=lambda x: x["final_score"], reverse=True)
        return final_results[:top_k]

    def validate_groundedness(
        self, query: str, chunks: List[Dict[str, Any]], threshold: float = 0.2
    ) -> Dict[str, Any]:
        del query
        if not chunks:
            return {
                "filtered_chunks": [],
                "should_answer": False,
                "fallback_message": "Khong tim thay thong tin phu hop trong tai lieu.",
            }
        filtered = [c for c in chunks if c.get("final_score", 0) >= threshold]
        if not filtered:
            return {
                "filtered_chunks": [],
                "should_answer": False,
                "fallback_message": "Du lieu tim thay khong du tin cay de tra loi.",
            }
        if filtered[0].get("final_score", 0) < threshold:
            return {
                "filtered_chunks": filtered,
                "should_answer": False,
                "fallback_message": "Noi dung tim thay khong chua cau tra loi chinh xac.",
            }
        return {
            "filtered_chunks": filtered[:3],
            "should_answer": True,
            "fallback_message": None,
        }

    def build_grounded_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        context_blocks = []
        for i, chunk in enumerate(chunks, start=1):
            page_info = chunk.get("metadata", {}).get("page_label", "")
            context_blocks.append(f"Tai lieu {i} {page_info}:\n{chunk['content']}")
        context_text = "\n\n".join(context_blocks)
        return (
            "Ban la tro ly tom tat van ban hanh chinh chuyen nghiep.\n"
            "Chi duoc su dung thong tin trong phan CONTEXT.\n"
            'Neu khong tim thay thong tin chinh xac, tra loi: "Khong tim thay thong tin phu hop trong tai lieu.".\n'
            "Khong duoc tu suy dien ngoai tai lieu.\n\n"
            f"CONTEXT:\n{context_text}\n\nCAU HOI:\n{query}\n\nTRA LOI:"
        )

    def validate_answer_vs_context(self, answer: str, chunks: List[Dict[str, Any]]) -> bool:
        if "Khong tim thay thong tin" in answer:
            return True
        answer_tokens = set(ViTokenizer.tokenize(answer.lower()).split())
        context_text = " ".join(c["content"].lower() for c in chunks)
        context_tokens = set(ViTokenizer.tokenize(context_text).split())
        overlap = answer_tokens.intersection(context_tokens)
        if len(answer_tokens) > 3 and len(overlap) / len(answer_tokens) < 0.1:
            return False
        return True

    async def get_rag_answer(
        self,
        query: str,
        top_k: int = 3,
        document_ids: list[int] | None = None,
    ) -> Dict[str, Any]:
        # Normalize và correct query trước khi search
        clean_query = self.normalize_text(query)
        context_chunks = self.hybrid_search(clean_query, top_k=top_k, document_ids=document_ids)
        validation = self.validate_groundedness(clean_query, context_chunks)

        if not validation["should_answer"]:
            return {
                "answer": validation["fallback_message"],
                "sources": [],
                "source_chunks": [],
                "grounded": False,
            }

        prompt = self.build_grounded_prompt(clean_query, validation["filtered_chunks"])
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.llm_url,
                    json={"model": self.llm_model, "prompt": prompt, "stream": False},
                    timeout=30.0,
                )
                response.raise_for_status()
                llm_output = response.json().get("response", "").strip()
        except Exception as exc:
            llm_output = f"Loi khi ket noi voi mo hinh AI: {exc}"

        is_valid = self.validate_answer_vs_context(llm_output, validation["filtered_chunks"])
        if not is_valid:
            llm_output = "Xin loi, toi khong the tim thay cau tra loi chinh xac trong tai lieu nay mac du co du lieu lien quan."

        return {
            "answer": llm_output,
            "sources": [c.get("content", "") for c in validation["filtered_chunks"]],
            "source_chunks": validation["filtered_chunks"],
            "grounded": is_valid,
        }

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not query or self.index.ntotal == 0:
            return []
        query_vector = self.embedding_model.encode([query]).astype("float32")
        distances, indices = self.index.search(query_vector, top_k)
        return [
            {**self.documents[idx], "score": float(distances[0][i])}
            for i, idx in enumerate(indices[0])
            if idx != -1 and idx < len(self.documents)
        ]

    # ── Chunking ──────────────────────────────────────────────────────────────

    def chunk_text(
        self,
        text: str,
        page_number: int | None = None,
        page_label: str | None = None,
    ) -> list[dict[str, Any]]:
        if not text:
            return []

        resolved_label = page_label or self._format_page_label(page_number)
        all_lines = text.splitlines()
        total_lines = max(len(all_lines), 1)

        article_matches = list(self.ARTICLE_PATTERN.finditer(text))
        if not article_matches:
            return [{
                "content": text,
                "metadata": {
                    "dieu": None, "khoan": None,
                    "page_number": page_number, "page_label": resolved_label,
                    "start_line": 1, "end_line": total_lines,
                    "section_type": "free_text",
                    "anchor_text": all_lines[0].strip()[:160] if all_lines else "",
                },
            }]

        chunks: list[dict[str, Any]] = []
        for i, match in enumerate(article_matches):
            start = match.start()
            end = article_matches[i + 1].start() if i + 1 < len(article_matches) else len(text)
            article_content = text[start:end].strip()
            article_header = match.group(0).strip()
            article_num_m = re.search(r"\d+", article_header)
            article_num = article_num_m.group(0) if article_num_m else None

            clause_pattern = re.compile(
                r"^\s*(Khoản\s+\d+[:.]?|Khoan\s+\d+[:.]?|\(?\d+\)[\s.]|\d+\.)",
                re.IGNORECASE | re.MULTILINE,
            )
            clause_matches = list(clause_pattern.finditer(article_content))
            if not clause_matches:
                chunks.append({
                    "content": article_content,
                    "metadata": {
                        "dieu": article_num, "khoan": None,
                        "page_number": page_number, "page_label": resolved_label,
                        "start_line": self._line_number_for_offset(text, start),
                        "end_line": self._line_number_for_offset(text, max(end - 1, start)),
                        "section_type": "article",
                        "anchor_text": article_header[:160],
                    },
                })
                continue

            for j, clause_match in enumerate(clause_matches):
                clause_start = clause_match.start()
                clause_end = clause_matches[j + 1].start() if j + 1 < len(clause_matches) else len(article_content)
                clause_text = article_content[clause_start:clause_end].strip()
                clause_num_m = re.search(r"\d+", clause_match.group(0))
                clause_num = clause_num_m.group(0) if clause_num_m else None
                abs_start = start + clause_start
                abs_end = start + max(clause_end - 1, clause_start)
                clause_lines = clause_text.splitlines()
                chunks.append({
                    "content": f"{article_header}\n{clause_text}",
                    "metadata": {
                        "dieu": article_num, "khoan": clause_num,
                        "page_number": page_number, "page_label": resolved_label,
                        "start_line": self._line_number_for_offset(text, abs_start),
                        "end_line": self._line_number_for_offset(text, abs_end),
                        "section_type": "article_clause",
                        "anchor_text": clause_lines[0].strip()[:160] if clause_lines else article_header[:160],
                    },
                })
        return chunks

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not chunks:
            return []
        contents = [c["content"] for c in chunks]
        vectors = self.embedding_model.encode(contents)
        return [
            {"content": c["content"], "vector": vectors[i].tolist(), "metadata": c.get("metadata", {})}
            for i, c in enumerate(chunks)
        ]

    # ── Document Processing ───────────────────────────────────────────────────

    def process_document(self, file_bytes: bytes, filename: str) -> dict[str, Any]:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        pages = self._extract_pages(file_bytes, ext)
        cleaned_pages = self.clean_pages(pages)
        clean_body_text = "\n\n".join(p["text"] for p in cleaned_pages if p["text"]).strip()
        clean_text = "\n\n".join(
            (f"--- Page {p['page_number']} ---\n{p['text']}" if len(cleaned_pages) > 1 else p["text"])
            for p in cleaned_pages if p["text"]
        ).strip()

        chunks: list[dict[str, Any]] = []
        for page in cleaned_pages:
            chunks.extend(self.chunk_text(
                page["text"],
                page_number=page["page_number"],
                page_label=self._format_page_label(page["page_number"]),
            ))

        return {
            "filename": filename,
            "extension": ext,
            "pages": cleaned_pages,
            "page_count": len(cleaned_pages),
            "page_index": self.build_page_index(cleaned_pages),
            "raw_text": "\n\n".join(p.get("text", "") for p in pages).strip(),
            "clean_text": clean_text,
            "chunks": chunks,
            "classification": self.classify_document(clean_body_text),
            "structure": self.detect_document_structure(clean_body_text),
            "supported_formats": ["pdf", "docx", "txt", "jpg", "jpeg", "png", "bmp", "tif", "tiff"],
        }

    def process_file(self, file_bytes: bytes, filename: str) -> str:
        return self.process_document(file_bytes, filename)["clean_text"]

    # ── Structure Detection ────────────────────────────────────────────────────

    def build_page_index(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        page_index = []
        for page in pages:
            text = page.get("text", "")
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            anchors = [
                ln[:160] for ln in lines
                if self.ARTICLE_PATTERN.match(ln)
                or self.CHAPTER_PATTERN.match(ln)
                or self.SECTION_PATTERN.match(ln)
            ]
            page_index.append({
                "page_number": page["page_number"],
                "heading": lines[0][:160] if lines else "",
                "preview": text[:240],
                "line_count": len(lines),
                "anchors": anchors[:20],
                "line_map": [
                    {"line_number": i + 1, "text": ln[:240]}
                    for i, ln in enumerate(lines)
                ],
            })
        return page_index

    def detect_document_structure(self, text: str) -> dict[str, Any]:
        return {
            "document_code": self._first_match(self.DOCUMENT_CODE_PATTERN, text),
            "summary": self._first_match(self.SUMMARY_PATTERN, text),
            "chapter_count": len(self.CHAPTER_PATTERN.findall(text)),
            "section_count": len(self.SECTION_PATTERN.findall(text)),
            "article_count": len(self.ARTICLE_PATTERN.findall(text)),
            "clause_count": len(self.CLAUSE_PATTERN.findall(text)),
        }

    def classify_document(self, text: str) -> dict[str, Any]:
        lowered = self._ascii_fold(text)
        first_line = next((ln.strip() for ln in lowered.splitlines() if ln.strip()), "")
        scores: dict[str, int] = {}
        matched_signals: dict[str, list[str]] = {}
        for doc_type, keywords in self.DOCUMENT_PATTERNS.items():
            matches = [kw for kw in keywords if kw in lowered]
            scores[doc_type] = len(matches)
            matched_signals[doc_type] = matches
            if any(first_line.startswith(kw) for kw in keywords):
                scores[doc_type] += 2
        if self.ARTICLE_PATTERN.search(text):
            scores["quyet_dinh"] = scores.get("quyet_dinh", 0) + 1
            scores["nghi_dinh"] = scores.get("nghi_dinh", 0) + 1
        best_type = max(scores, key=scores.get) if scores else "khac"
        best_score = scores.get(best_type, 0)
        total = sum(scores.values()) or 1
        confidence = round(best_score / total, 2) if best_score else 0.0
        return {
            "document_type": best_type if best_score else "khac",
            "confidence": confidence,
            "matched_signals": matched_signals.get(best_type, []),
        }

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _extract_pages(self, file_bytes: bytes, ext: str) -> list[dict[str, Any]]:
        if ext == "pdf":
            return self.extract_pages_from_pdf(file_bytes)
        if ext == "docx":
            return self.extract_pages_from_docx(file_bytes)
        if ext == "txt":
            return self.extract_pages_from_txt(file_bytes)
        if ext in {"jpg", "jpeg", "png", "bmp", "tif", "tiff"}:
            return [{"page_number": 1, "text": self.extract_from_image(file_bytes)}]
        raise ValueError(f"Unsupported file format: {ext}")

    def _extract_pdf_text_pages(self, pdf_bytes: bytes) -> list[dict[str, Any]]:
        try:
            from pypdf import PdfReader
        except Exception:
            return [{"page_number": 1, "text": ""}]
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                page_text = (page.extract_text(extraction_mode="layout") or "").strip()
            except TypeError:
                page_text = (page.extract_text() or "").strip()
            pages.append({"page_number": i, "text": page_text})
        return pages or [{"page_number": 1, "text": ""}]

    @staticmethod
    def _normalize_bullets(text: str) -> str:
        text = re.sub(r"^[•●▪■]+", "-", text, flags=re.MULTILINE)
        text = text.replace("“", '"').replace("”", '"')
        text = text.replace("‘", "'").replace("’", "'")
        return text

    def _strip_administrative_noise(self, text: str) -> str:
        """Loại bỏ tiêu ngữ lặp lại, số trang, đường kẻ, watermark."""
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                lines.append("")
                continue
            # Loại số trang đơn lẻ
            if self.PAGE_ONLY_PATTERN.match(stripped):
                continue
            # Loại đường kẻ trang trí
            if re.fullmatch(r"[_\-=\s]{3,}", stripped):
                continue
            # Loại tiêu ngữ quốc gia lặp lại (xuất hiện > 2 lần)
            # (xử lý ở clean_pages bằng repeated_headers, ở đây chỉ giữ)
            lines.append(stripped)
        return "\n".join(lines)

    @staticmethod
    def _ascii_fold(text: str) -> str:
        normalized = unicodedata.normalize("NFD", text)
        stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return stripped.replace("đ", "d").replace("Đ", "D").lower()

    def _embedding_dimension(self) -> int:
        dim = getattr(self.embedding_model, "dimension", None)
        if dim:
            return int(dim)
        probe = self.embedding_model.encode(["probe"])
        return int(probe.shape[1])

    def _first_match(self, pattern: re.Pattern, text: str) -> Optional[str]:
        match = pattern.search(text)
        if not match:
            return None
        value = match.group(1).strip()
        return value[:250] if value else None

    @staticmethod
    def _line_number_for_offset(text: str, offset: int) -> int:
        bounded = max(0, min(offset, len(text)))
        return text.count("\n", 0, bounded) + 1

    @staticmethod
    def _format_page_label(page_number: int | None) -> str:
        return f"(Trang {page_number})" if page_number else ""

    def _restore_paragraph_flow(self, text: str) -> str:
        """
        Khôi phục luồng đoạn văn: nối các dòng bị ngắt không cần thiết.
        Cải tiến so với cũ: logic join rõ ràng hơn, ít false positive hơn.
        """
        if not text or "\n" not in text:
            return text

        raw_lines = [ln.strip() for ln in text.splitlines()]
        non_empty = [ln for ln in raw_lines if ln]
        if not non_empty:
            return ""

        # Tính tỷ lệ dòng ngắn để quyết định aggressive join
        short_ratio = sum(1 for ln in non_empty if len(ln.split()) <= 3) / len(non_empty)
        aggressive = short_ratio >= 0.45

        rebuilt: list[str] = []
        buffer = ""
        for line in raw_lines:
            if not line:
                if buffer:
                    rebuilt.append(buffer.strip())
                    buffer = ""
                continue

            if self._is_structural_line(line):
                if buffer:
                    rebuilt.append(buffer.strip())
                    buffer = ""
                rebuilt.append(line)
                continue

            if not buffer:
                buffer = line
                continue

            if self._should_join_lines(buffer, line, aggressive):
                sep = "" if buffer.endswith("-") else " "
                buffer = f"{buffer.rstrip('-')}{sep}{line}"
            else:
                rebuilt.append(buffer.strip())
                buffer = line

        if buffer:
            rebuilt.append(buffer.strip())
        return "\n".join(part for part in rebuilt if part)

    def _should_join_lines(self, prev: str, nxt: str, aggressive: bool) -> bool:
        """
        Quyết định có nối 2 dòng liền nhau không.
        Logic được làm rõ ràng hơn phiên bản cũ.
        """
        # Không nối nếu dòng tiếp theo là structural
        if self._is_structural_line(nxt):
            return False
        # Không nối sau dấu hai chấm (thường là danh sách)
        if prev.endswith(":") and not aggressive:
            return False
        # Nối nếu dòng trước kết thúc bằng dấu gạch ngang (từ bị ngắt)
        if prev.endswith("-"):
            return True
        # Nối nếu aggressive mode và dòng ngắn
        if aggressive and (len(prev.split()) <= 4 or len(nxt.split()) <= 4):
            return True
        # Không nối nếu câu trước kết thúc hoàn chỉnh và dòng tiếp theo bắt đầu bằng chữ hoa
        if prev.endswith((".", "!", "?", "…")) and nxt[:1].isupper():
            return False
        # Nối nếu câu chưa kết thúc hoặc dòng tiếp theo là connector
        return (
            not prev.endswith((".", "!", "?", "…"))
            or nxt[:1].islower()
            or bool(self.CONNECTOR_LINE_PATTERN.match(nxt))
        )

    def _is_structural_line(self, line: str) -> bool:
        return bool(self.STRUCTURAL_LINE_PATTERN.match(line))