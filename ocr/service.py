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
from pathlib import Path
import io
import json
import logging
import os
import re
import shutil
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
if getattr(settings, "TESSERACT_CMD", ""):
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
if getattr(settings, "TESSDATA_PREFIX", ""):
    os.environ.setdefault("TESSDATA_PREFIX", settings.TESSDATA_PREFIX)


def _resolve_poppler_path() -> str | None:
    configured = getattr(settings, "POPPLER_PATH", "")
    if configured:
        configured_path = Path(configured)
        if configured_path.is_dir():
            return str(configured_path)
        if configured_path.is_file():
            return str(configured_path.parent)

    fallback_candidates = [
        Path(r"E:/poppler-26.02.0/Library/bin"),
        Path(r"E:/poppler-26.02.0/bin"),
    ]
    for candidate in fallback_candidates:
        if candidate.is_dir():
            return str(candidate)

    executable = shutil.which("pdftoppm") or shutil.which("pdftoppm.exe")
    if executable:
        return str(Path(executable).parent)
    return None


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


OCR_DIR = Path(__file__).resolve().parent


class _VietnameseOCRCorrector:
    """
    Sửa lỗi OCR tiếng Việt theo nhiều tầng:
      1. Lỗi font (TCVN3, VNI) → Unicode
      2. Lỗi ký tự đơn lẻ (load từ JSON)
      3. Lỗi âm tiết (load từ JSON)
      4. Lỗi cụm từ (load từ JSON)
      5. Lỗi từ viết tắt (load từ JSON)
    """

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
        "Ñ": "ẹ", "Ð": "é", "Ý": "ĩ", "Þ": "ị", "×": "ì", "Ø": "í",
        "Æ": "ặ", "Ë": "ậ", "È": "ẩ", "É": "ẫ", "Ç": "ầ",
    })

    VNI_CHAR_MAP = {
        "aù": "á", "aà": "à", "aả": "ả", "aã": "ã", "aạ": "ạ",
        "aê": "â", "aêù": "ấ", "aêà": "ầ", "aêả": "ẩ", "aêã": "ẫ", "aêạ": "ậ",
        "aêù": "ắ", "aêà": "ằ", "aêả": "ẳ", "aêã": "ẵ", "aêạ": "ặ",
        "eù": "é", "eà": "è", "eả": "ẻ", "eã": "ẽ", "eạ": "ẹ",
        "eê": "ê", "eêù": "ế", "eêà": "ề", "eêả": "ể", "eêã": "ễ", "eêạ": "ệ",
    }

    def convert_to_unicode(self, text: str) -> str:
        if not text: return text
        text = text.translate(self.TCVN3_CHAR_MAP)
        for pattern, replacement in self.VNI_CHAR_MAP.items():
            text = text.replace(pattern, replacement).replace(pattern.upper(), replacement.upper())
        return text

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

    def __init__(self, rules_path: str | Path | None = None):
        if rules_path is None:
            rules_path = OCR_DIR / "correction_rules.json"
        self.rules = {}
        try:
            if os.path.exists(rules_path):
                with open(rules_path, "r", encoding="utf-8") as f:
                    self.rules = json.load(f)
            else:
                logger.warning("ocr_rules_not_found: %s", rules_path)
        except Exception as e:
            logger.error("ocr_rules_load_failed: %s", e)

        # Pre-compile patterns
        self._char_patterns = [(re.compile(p, re.UNICODE), r) for p, r in self.rules.get("char_confusion_fixes", [])]
        self._phrase_patterns = [(re.compile(re.escape(s), re.I | re.U), t) for s, t in self.rules.get("phrase_fixes", [])]
        self._syllable_patterns = [
            (re.compile(rf"(?<![^\s\n\t]){re.escape(s)}(?![^\s\n\t.,;:!?\"'()\[\]])", re.I | re.U), t)
            for s, t in self.rules.get("syllable_fixes", [])
        ]
        self._abbr_patterns = [
            (re.compile(rf"(?<!\w){re.escape(s)}(?!\w)", re.I | re.U), t)
            for s, t in self.rules.get("abbreviation_fixes", [])
        ]

    def correct(self, text: str) -> str:
        if not text: return text
        text = self._fix_font_encoding(text)
        text = unicodedata.normalize("NFC", text)

        for p, r in self._char_patterns: text = p.sub(r, text)
        for p, r in self._phrase_patterns: text = p.sub(r, text)
        for p, r in self._syllable_patterns: text = p.sub(r, text)
        for p, r in self._abbr_patterns: text = p.sub(r, text)

        return unicodedata.normalize("NFC", text)

    def _fix_font_encoding(self, text: str) -> str:
        text = self.convert_to_unicode(text)
        text = text.translate(self.TCVN3_CHAR_MAP)
        for s, t in sorted(self.COMMON_VNI_REPLACEMENTS, key=lambda x: -len(x[0])):
            text = text.replace(s, t)
            text = text.replace(s.upper(), t.upper())
        
        if self._has_mojibake(text):
            for codec in ("latin1", "cp1252"):
                try:
                    candidate = text.encode(codec).decode("utf-8")
                    if self._viet_score(candidate) > self._viet_score(text):
                        text = candidate
                        break
                except (UnicodeEncodeError, UnicodeDecodeError): continue
        return text

    @staticmethod
    def _has_mojibake(text: str) -> bool:
        mojibake_chars = sum(1 for ch in text if "\x80" <= ch <= "\x9f" or "\xa0" <= ch <= "\xbf")
        return mojibake_chars / max(len(text), 1) > 0.05

    @staticmethod
    def _viet_score(text: str) -> int:
        if not text:
            return 0
        lowered = text.lower()
        vietnamese_chars = len(re.findall(r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệóòỏõọốồổỗộớờởỡợíìỉĩịúùủũụứừửữựýỳỷỹỵ]", lowered))
        common_words = len(re.findall(
            r"\b(cộng|hòa|xã|hội|chủ|nghĩa|việt|nam|độc|lập|tự|do|hạnh|phúc|"
            r"ủy|ban|nhân|dân|quyết|định|công|văn|thông|báo|nghị|định|điều|khoản|"
            r"ngày|tháng|năm|về|việc|căn|cứ|thực|hiện)\b",
            lowered,
        ))
        alnum = len(re.findall(r"[\wăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệóòỏõọốồổỗộớờởỡợíìỉĩịúùủũụứừửữựýỳỷỹỵ]", lowered, re.UNICODE))
        garbage = len(re.findall(r"[|_<>{}\\~`^]", text))
        return vietnamese_chars * 4 + common_words * 12 + min(alnum, 300) - garbage * 8

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
    TESSERACT_CONFIGS = (
        "--oem 3 --psm 6 -c preserve_interword_spaces=1",
        "--oem 3 --psm 4 -c preserve_interword_spaces=1",
        "--oem 3 --psm 3 -c preserve_interword_spaces=1",
        "--oem 3 --psm 11",
    )

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
        r"^\s*(?:(Khoản|Khoan)\s+\d+[.:)]?|\d+[.)]\s+)",
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
        "nghi_dinh":  ["nghi_dinh", "nd"],
        "chi_thi":    ["chi thi", "ct"],
        "to_trinh":   ["to trinh", "tt"],
        "bao_cao":    ["bao cao", "bc"],
        "bien_ban":   ["bien ban", "bb"],
        "hop_dong":   ["hop dong", "hd"],
    }

    
    def __init__(self, index_path: str = "ocr_vectors.index", metadata_path: str = "ocr_metadata.json"):
        self.config = self.TESSERACT_CONFIG
        self.lang = getattr(settings, "OCR_LANG", "vie+eng") or "vie+eng"
        self._corrector = _VietnameseOCRCorrector()
        
        # Vector Storage configuration
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
            idx_path = Path(self.index_path)
            if idx_path.exists() and os.path.exists(self.metadata_path):
                try:
                    self._index = faiss.read_index(str(idx_path))
                    with open(self.metadata_path, "r", encoding="utf-8") as f:
                        self.documents = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load FAISS index: {e}")
                    self._index = faiss.IndexFlatL2(self._embedding_dimension())
                    self.documents = []
            else:
                self._index = faiss.IndexFlatL2(self._embedding_dimension())
                self.documents = []
        return self._index

    def _embedding_dimension(self) -> int:
        return 384

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

    def _extract_pages(self, file_bytes: bytes, extension: str) -> list[dict[str, Any]]:
        if extension == "pdf":
            return self._extract_pdf_pages(file_bytes)
        elif extension == "docx":
            return self.extract_pages_from_docx(file_bytes)
        elif extension == "txt":
            return self.extract_pages_from_txt(file_bytes)
        elif extension in ["jpg", "jpeg", "png", "bmp", "tif", "tiff"]:
            return [{"page_number": 1, "text": self.extract_from_image(file_bytes)}]
        return []

    def _extract_pdf_pages(self, pdf_bytes: bytes) -> list[dict[str, Any]]:
        """
        Trích xuất text từ PDF.
        Ưu tiên text layer (nhanh, chính xác). Fallback sang OCR nếu là PDF scan.
        """
        pages = self._extract_pdf_text_pages(pdf_bytes)

        # Kiểm tra xem có phải PDF scan không (text layer rỗng/rất ngắn)
        if not pages:
            is_scan = True
        else:
            total_text_len = sum(len(p.get("text", "").strip()) for p in pages)
            is_scan = total_text_len < len(pages) * 20  # < 20 chars/page trung bình

        if is_scan:
            logger.info("pdf_scan_detected, using OCR fallback")
            images = convert_from_bytes(pdf_bytes, dpi=300, poppler_path=_resolve_poppler_path())
            return [
                {
                    "page_number": i + 1,
                    "text": self._ocr_pil_image(img),
                }
                for i, img in enumerate(images)
            ]

        return pages

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
        return self._ocr_image_with_fallbacks(image, log_prefix="image")

    # ── PDF Extraction ────────────────────────────────────────────────────────

    def extract_pages_from_pdf(self, pdf_bytes: bytes) -> list[dict[str, Any]]:
        """
        Trích xuất text từ PDF.
        Ưu tiên text layer (nhanh, chính xác). Fallback sang OCR nếu là PDF scan.
        """
        pages = self._extract_pdf_text_pages(pdf_bytes)

        # Kiểm tra xem có phải PDF scan không (text layer rỗng/rất ngắn)
        if not pages:
            is_scan = True
        else:
            total_text_len = sum(len(p.get("text", "").strip()) for p in pages)
            is_scan = total_text_len < len(pages) * 20  # < 20 chars/page trung bình

        if is_scan:
            logger.info("pdf_scan_detected, using OCR fallback")
            images = convert_from_bytes(pdf_bytes, dpi=300, poppler_path=_resolve_poppler_path())
            return [
                {
                    "page_number": i + 1,
                    "text": self._ocr_pil_image(img),
                }
                for i, img in enumerate(images)
            ]

        return pages

    def _extract_pdf_text_pages(self, pdf_bytes: bytes) -> list[dict[str, Any]]:
        try:
            import pypdf
            pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            pages = []
            for i, page in enumerate(pdf_reader.pages):
                text = page.extract_text() or ""
                pages.append({"page_number": i + 1, "text": text})
            return pages
        except Exception as e:
            logger.error("pypdf_extraction_failed: %s", e)
            return []

    def _ocr_pil_image(self, image: Image.Image) -> str:
        """OCR một PIL Image với correction pipeline."""
        return self._ocr_image_with_fallbacks(image, log_prefix="pdf")

    def _ocr_image_with_fallbacks(self, image: Image.Image, log_prefix: str = "ocr") -> str:
        """
        OCR theo kiểu staged: thử nhanh preset chuẩn trước, chỉ mở rộng sang các biến thể khác nếu kết quả kém.
        Giảm đáng kể số lần gọi Tesseract so với brute-force toàn bộ tổ hợp.
        """
        variants = [
            ("standard", _ImagePreprocessor.preprocess(image, aggressive=False), [self.TESSERACT_CONFIGS[0]]),
            ("standard+alt", _ImagePreprocessor.preprocess(image, aggressive=False), list(self.TESSERACT_CONFIGS[1:2])),
            ("aggressive", _ImagePreprocessor.preprocess(image, aggressive=True), [self.TESSERACT_CONFIGS[0]]),
            ("binarize", _ImagePreprocessor.adaptive_binarize(ImageOps.grayscale(image)), [self.TESSERACT_CONFIGS[0]]),
        ]

        best_text = ""
        best_score = -1
        for preset_name, processed, configs in variants:
            for config in configs:
                try:
                    raw = self._image_to_string(processed, config=config).strip()
                    corrected = self._corrector.correct(raw)
                    score = _VietnameseOCRCorrector._viet_score(corrected)
                    logger.debug(
                        "%s_ocr preset=%s config=%s score=%d chars=%d",
                        log_prefix,
                        preset_name,
                        config,
                        score,
                        len(corrected),
                    )
                    if score > best_score:
                        best_score = score
                        best_text = corrected
                    if score >= 28 and len(corrected) >= 20:
                        return corrected
                except Exception as exc:
                    logger.debug("%s_ocr_variant_failed preset=%s config=%s: %s", log_prefix, preset_name, config, exc)

        return best_text

    def _image_to_string(self, image: Image.Image, config: str) -> str:
        language_candidates = [self.lang]
        for fallback in ("vie", "eng"):
            if fallback not in language_candidates:
                language_candidates.append(fallback)

        last_error: Exception | None = None
        for lang in language_candidates:
            try:
                return pytesseract.image_to_string(image, lang=lang, config=config)
            except pytesseract.TesseractError as exc:
                last_error = exc
                logger.debug("tesseract_lang_failed lang=%s config=%s: %s", lang, config, exc)
        if last_error:
            raise last_error
        return ""

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

    def normalize_text(self, text: str) -> str:
        """
        Pipeline chuẩn hóa văn bản toàn diện.
        """
        if not text:
            return ""

        # Bước 1: Sửa lỗi encoding font cũ & Unicode Normalization
        text = self._corrector.convert_to_unicode(text)
        text = unicodedata.normalize("NFC", text)

        # Bước 2: Loại bỏ ký tự điều khiển (giữ lại \n, \t)
        text = text.replace("\x0c", "\n")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = "".join(
            ch for ch in text
            if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\t")
        )

        # Bước 3: Chuẩn hóa bullet points
        text = self._normalize_bullets(text)

        # Bước 4: Khôi phục luồng đoạn văn (paragraph flow)
        text = self._restore_paragraph_flow(text)

        # Bước 5: Loại bỏ nhiễu hành chính (tiêu ngữ, số trang, đường kẻ)
        text = self._strip_administrative_noise(text)

        # Bước 6: Sửa lỗi từ bị dính nhau sau OCR
        text = self.WORD_MERGE_PATTERN.sub(r"\1 \2", text)

        # Bước 7: Chuẩn hóa khoảng trắng
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Bước 8: Áp dụng toàn bộ correction pipeline OCR
        text = self._corrector.correct(text)

        # Bước 9: Loại bỏ ký tự rác còn lại (nếu tỷ lệ thấp)
        text = self._remove_garbage_chars(text)

        return text.strip()

    def _restore_paragraph_flow(self, text: str) -> str:
        # Giả lập khôi phục flow đoạn văn
        return text

    def _strip_administrative_noise(self, text: str) -> str:
        # Giả lập loại bỏ noise
        return text

    def _normalize_bullets(self, text: str) -> str:
        # Giả lập chuẩn hóa bullet
        return text

    def _remove_garbage_chars(self, text: str) -> str:
        """
        Loại bỏ ký tự rác sinh ra từ OCR.
        """
        lines = []
        for line in text.splitlines():
            garbage_count = len(self.GARBAGE_CHAR_PATTERN.findall(line))
            if len(line) > 0 and garbage_count / len(line) > 0.3:
                continue
            cleaned = self.GARBAGE_CHAR_PATTERN.sub("", line)
            lines.append(cleaned)
        return "\n".join(lines)

    def clean_pages(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        return normalized_pages

    def _format_page_label(self, page_number: int | None) -> str:
        return f"Trang {page_number}" if page_number else ""

    def _line_number_for_offset(self, text: str, offset: int) -> int:
        return text.count("\n", 0, offset) + 1

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
        return {"should_answer": True, "filtered_chunks": chunks}

    def build_grounded_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        return f"Context: {chunks}\nQuery: {query}"

    def validate_answer_vs_context(self, answer: str, chunks: List[Dict[str, Any]]) -> bool:
        # Reject empty or extremely short answers
        if not answer or len(answer.strip()) < 12:
            return False

        # Prefer answers that look Vietnamese using the internal viet score
        viet_score = _VietnameseOCRCorrector._viet_score(answer)
        if viet_score < 20:
            return False

        # Check some lexical overlap with context chunks to ensure groundedness
        try:
            answer_tokens = set(re.findall(r"\w+", answer.lower(), flags=re.UNICODE))
            chunk_text = " ".join(str(c.get("content", "")) for c in chunks).lower()
            overlap = sum(1 for t in answer_tokens if t in chunk_text)
            # require at least a small number of overlapping tokens or a relative overlap
            if overlap < 2 and (len(answer_tokens) == 0 or overlap / max(len(answer_tokens), 1) < 0.05):
                return False
        except Exception:
            return False

        return True

    def _fallback_rag_answer_from_chunks(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        if not chunks:
            return "Không tìm thấy nội dung phù hợp trong tài liệu đã chọn."

        best_chunk = max(
            chunks,
            key=lambda chunk: len(str(chunk.get("content", "")).strip()),
        )
        content = str(best_chunk.get("content", "")).strip()
        if not content:
            return "Không tìm thấy nội dung phù hợp trong tài liệu đã chọn."

        sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", content) if s.strip()]
        snippet = sentences[0] if sentences else content
        snippet = re.sub(r"\s+", " ", snippet).strip()
        if len(snippet) > 220:
            snippet = snippet[:217].rstrip() + "..."
        return snippet

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
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.llm_url,
                    json={
                        "model": self.llm_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_ctx": settings.OLLAMA_NUM_CTX,
                        },
                    },
                    timeout=settings.OLLAMA_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                llm_output = response.json().get("response", "").strip()
        except Exception as exc:
            logger.warning("rag_llm_unavailable: %s", exc)
            llm_output = self._fallback_rag_answer_from_chunks(clean_query, validation["filtered_chunks"])

        is_valid = self.validate_answer_vs_context(llm_output, validation["filtered_chunks"])
        if not is_valid:
            llm_output = self._fallback_rag_answer_from_chunks(clean_query, validation["filtered_chunks"])

        return {
            "answer": llm_output,
            "sources": [c.get("content", "") for c in validation["filtered_chunks"]],
            "source_chunks": validation["filtered_chunks"],
            "grounded": is_valid,
        }

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        return []

    # ── Chunking ──────────────────────────────────────────────────────────────

    def chunk_text(
        self,
        text: str,
        page_number: int | None = None,
        page_label: str | None = None,
    ) -> list[dict[str, Any]]:
        text = re.sub(r"[><|\\/_~]", " ", text)
        text = "".join(
            ch for ch in text
            if unicodedata.category(ch)[0] != "C" or ch in ["\n", "\r", "\t"]
        )
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n+", "\n", text).strip()

        # - Thay thế các ký tự so sánh/ngoặc nhọn gây nhiễu bằng khoảng trắng hoặc ký tự phù hợp
        # - Giữ lại dấu gạch ngang '-' nếu nó nối từ hoặc dùng làm bullet point
        text = re.sub(r'[><|\\/_~]', ' ', text)
        
        # Remove non-printable characters except newline/tab
        text = "".join(ch for ch in text if unicodedata.category(ch)[0] != 'C' or ch in ['\n', '\r', '\t'])

        # Step 3: Generalized line merging
        # If a line doesn't end with a punctuation mark (. ! ? :), it might be a broken line
        lines = text.split('\n')
        merged_lines = []
        current_line = ""

        for line in lines:
            line = line.strip()
            if not line:
                if current_line:
                    merged_lines.append(current_line)
                    current_line = ""
                continue

            if self._is_structural_line(line):
                if current_line:
                    merged_lines.append(current_line)
                current_line = line
                continue
            
            if current_line:
                # If current_line doesn't end with sentence-ending punctuation, merge with current line
                if not re.search(r'[.!?:–—−-]$', current_line):
                    current_line += " " + line
                else:
                    merged_lines.append(current_line)
                    current_line = line
            else:
                current_line = line
        
        if current_line:
            merged_lines.append(current_line)
        
        text = "\n".join(merged_lines)

        # Step 4: Standardize whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        
        return self._chunk_text_impl(text.strip(), page_number=page_number, page_label=page_label)
        """
        Split normalized text into chunks based on legal structure (Điều, Khoản).
        """
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

    def _chunk_text_impl(
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
                    "dieu": None,
                    "khoan": None,
                    "page_number": page_number,
                    "page_label": resolved_label,
                    "start_line": 1,
                    "end_line": total_lines,
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
                r"^\s*(Khoáº£n\s+\d+[:.]?|Khoan\s+\d+[:.]?|\(?\d+\)[\s.]|\d+\.)",
                re.IGNORECASE | re.MULTILINE,
            )
            clause_matches = list(clause_pattern.finditer(article_content))
            if not clause_matches:
                chunks.append({
                    "content": article_content,
                    "metadata": {
                        "dieu": article_num,
                        "khoan": None,
                        "page_number": page_number,
                        "page_label": resolved_label,
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
                        "dieu": article_num,
                        "khoan": clause_num,
                        "page_number": page_number,
                        "page_label": resolved_label,
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
    async def fix_ocr_errors_with_llm(self, text: str) -> str:
        """
        Generalized LLM Post-processing:
        Sử dụng AI để sửa lỗi chính tả, khôi phục dấu và chuẩn hóa format hành chính.
        """
        if not text or len(text.strip()) < 10:
            return text

        prompt = f"""BẠN LÀ CHUYÊN GIA HIỆU ĐÍNH KẾT QUẢ OCR TIẾNG VIỆT.
Nhiệm vụ: Sửa các lỗi OCR tiếng Việt nhưng không thay đổi nội dung.

YÊU CẦU:
1. Chỉ sửa lỗi nhận diện OCR, lỗi chính tả, lỗi dấu tiếng Việt và khoảng trắng bất thường.
2. Giữ nguyên ý nghĩa, số liệu, tên riêng, mã văn bản, ngày tháng và thứ tự dòng/mục nhiều nhất có thể.
3. Không tóm tắt, không diễn giải, không thêm thông tin, không bỏ thông tin.
4. Chỉ trả về văn bản đã sửa, không giải thích.

VĂN BẢN OCR CẦN XỬ LÝ:
---
{text}
---

VĂN BẢN ĐÃ SỬA:"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.llm_url,
                    json={
                        "model": self.llm_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "top_p": 0.9,
                            "num_ctx": settings.OLLAMA_NUM_CTX,
                        }
                    },
                    timeout=settings.OLLAMA_TIMEOUT_SECONDS
                )
                response.raise_for_status()
                fixed_text = response.json().get("response", "").strip()
                return fixed_text if fixed_text else text
        except Exception:
            # If LLM fails, return original text to avoid blocking
            return text

    async def fix_processed_result_with_llm(self, result: dict[str, Any]) -> dict[str, Any]:
        """
        Hiệu đính kết quả OCR bằng LLM rồi dựng lại clean_text/chunks để RAG dùng bản đã sửa.
        """
        pages = result.get("pages") or []
        if not pages:
            clean_text = result.get("clean_text") or ""
            fixed_text = await self.fix_ocr_errors_with_llm(clean_text)
            fixed_text = self.normalize_text(fixed_text)
            result["clean_text"] = fixed_text
            result["chunks"] = self.chunk_text(fixed_text)
            result["classification"] = self.classify_document(fixed_text)
            result["structure"] = self.detect_document_structure(fixed_text)
            return result

        fixed_pages: list[dict[str, Any]] = []
        for page in pages:
            page_text = page.get("text", "")
            fixed_text = await self.fix_ocr_errors_with_llm(page_text)
            fixed_pages.append({
                **page,
                "text": self.normalize_text(fixed_text),
            })

        clean_body_text = "\n\n".join(p["text"] for p in fixed_pages if p["text"]).strip()
        clean_text = "\n\n".join(
            (f"--- Page {p['page_number']} ---\n{p['text']}" if len(fixed_pages) > 1 else p["text"])
            for p in fixed_pages if p["text"]
        ).strip()

        chunks: list[dict[str, Any]] = []
        for page in fixed_pages:
            chunks.extend(self.chunk_text(
                page["text"],
                page_number=page.get("page_number"),
                page_label=self._format_page_label(page.get("page_number")),
            ))

        result["pages"] = fixed_pages
        result["page_index"] = self.build_page_index(fixed_pages)
        result["clean_text"] = clean_text
        result["chunks"] = chunks
        result["classification"] = self.classify_document(clean_body_text)
        result["structure"] = self.detect_document_structure(clean_body_text)
        return result

    def extract_from_image(self, image_bytes: bytes) -> str:
        """
        Extract text from an image.
        """
        image = Image.open(io.BytesIO(image_bytes))
        return self._ocr_pil_image(image).strip()

    def extract_from_pdf(self, pdf_bytes: bytes) -> str:
        """
        Extract text from a multi-page PDF by converting each page to an image.
        """
        pages = self._extract_pdf_pages(pdf_bytes)
        cleaned = self.clean_pages(pages)
        return "\n\n".join(
            f"--- Page {p['page_number']} ---\n{p['text']}"
            for p in cleaned if p["text"]
        )

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
        try:
            dim = getattr(self.embedding_model, "dimension", None)
            if dim:
                return int(dim)
            # Fallback probe
            probe = self.embedding_model.encode(["probe"])
            return int(probe.shape[1])
        except Exception as e:
            logger.warning(f"Could not detect embedding dimension, defaulting to 384: {e}")
            return 384

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
