import io
import json
import logging
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from typing import Any, Dict, List

import httpx
import numpy as np
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pyvi import ViTokenizer


logger = logging.getLogger(__name__)


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


class OCRService:
    TCVN3_CHAR_MAP = str.maketrans(
        {
            "µ": "à",
            "¸": "á",
            "¶": "ả",
            "·": "ã",
            "¹": "ạ",
            "¨": "ă",
            "»": "ằ",
            "¾": "ắ",
            "¼": "ẳ",
            "½": "ẵ",
            "Æ": "ặ",
            "©": "â",
            "Ç": "ầ",
            "Ê": "ấ",
            "È": "ẩ",
            "É": "ẫ",
            "Ë": "ậ",
            "Ì": "è",
            "Ð": "é",
            "Î": "ẻ",
            "Ï": "ẽ",
            "Ñ": "ẹ",
            "ª": "ê",
            "Ò": "ề",
            "Õ": "ế",
            "Ó": "ể",
            "Ô": "ễ",
            "Ö": "ệ",
            "×": "ì",
            "Ø": "í",
            "Ü": "ỉ",
            "Ý": "ĩ",
            "Þ": "ị",
            "ß": "ò",
            "ã": "ó",
            "á": "ỏ",
            "â": "õ",
            "ä": "ọ",
            "¬": "ơ",
            "å": "ờ",
            "ç": "ớ",
            "æ": "ở",
            "è": "ỡ",
            "é": "ợ",
            "ê": "ù",
            "ë": "ú",
            "ì": "ủ",
            "í": "ũ",
            "î": "ụ",
            "ï": "ỳ",
            "ó": "ý",
            "ñ": "ỷ",
            "ò": "ỹ",
            "ô": "ỵ",
            "­": "ư",
            "ø": "ừ",
            "ö": "ứ",
            "÷": "ử",
            "ù": "ữ",
            "ú": "ự",
            "¡": "Ă",
            "¢": "Â",
            "§": "Đ",
            "£": "Ê",
            "¤": "Ô",
            "¥": "Ơ",
            "¦": "Ư",
            "µ".upper(): "À",
            "¸".upper(): "Á",
            "¶".upper(): "Ả",
            "·".upper(): "Ã",
            "¹".upper(): "Ạ",
        }
    )

    COMMON_VNI_REPLACEMENTS = [
        ("aø", "à"),
        ("aù", "á"),
        ("aû", "ả"),
        ("aõ", "ã"),
        ("aï", "ạ"),
        ("aê", "ă"),
        ("aâ", "â"),
        ("eø", "è"),
        ("eù", "é"),
        ("eû", "ẻ"),
        ("eõ", "ẽ"),
        ("eï", "ẹ"),
        ("eâ", "ê"),
        ("oø", "ò"),
        ("où", "ó"),
        ("oû", "ỏ"),
        ("oõ", "õ"),
        ("oï", "ọ"),
        ("oâ", "ô"),
        ("ôø", "ồ"),
        ("ôù", "ố"),
        ("ôû", "ổ"),
        ("ôõ", "ỗ"),
        ("ôï", "ộ"),
        ("uø", "ù"),
        ("uù", "ú"),
        ("uû", "ủ"),
        ("uõ", "ũ"),
        ("uï", "ụ"),
        ("ö", "ư"),
        ("yø", "ỳ"),
        ("yù", "ý"),
        ("yû", "ỷ"),
        ("yõ", "ỹ"),
        ("yï", "ỵ"),
        ("ñ", "đ"),
    ]

    DOCUMENT_PATTERNS: dict[str, list[str]] = {
        "cong_van": ["cong van", "kinh gui", "v/v", "ve viec"],
        "thong_bao": ["thong bao", "tran trong thong bao"],
        "quyet_dinh": ["quyet dinh", "quyet nghi", "ban hanh"],
        "nghi_dinh": ["nghi dinh", "chinh phu"],
        "bao_cao": ["bao cao", "ket qua", "tong hop"],
        "to_trinh": ["to trinh", "kinh trinh"],
        "bien_ban": ["bien ban", "thanh phan tham du"],
    }

    PAGE_ONLY_PATTERN = re.compile(r"^(trang|page)?\s*\d+(\s*/\s*\d+)?$", re.IGNORECASE)
    DOCUMENT_CODE_PATTERN = re.compile(r"\b(?:số|so)\s*[:.]?\s*([0-9A-Z][0-9A-Z/.-]{2,})", re.IGNORECASE)
    SUMMARY_PATTERN = re.compile(r"\b(?:về việc|ve viec|trích yếu|trich yeu)\b[:\s-]*(.+)", re.IGNORECASE)
    ARTICLE_PATTERN = re.compile(r"^\s*(Điều|Dieu)\s+\d+[:.]?", re.IGNORECASE | re.MULTILINE)
    CHAPTER_PATTERN = re.compile(r"^\s*(Chương|Chuong)\s+[IVXLC0-9]+", re.IGNORECASE | re.MULTILINE)
    SECTION_PATTERN = re.compile(r"^\s*(Mục|Muc|Phần|Phan)\s+[IVXLC0-9]+", re.IGNORECASE | re.MULTILINE)
    CLAUSE_PATTERN = re.compile(r"^\s*(Khoản\s+\d+|Khoan\s+\d+|\(?\d+\))", re.IGNORECASE | re.MULTILINE)

    def __init__(self, index_path: str = "ocr_vectors.index", metadata_path: str = "ocr_metadata.json"):
        self.config = "--oem 3 --psm 6"
        self.lang = "vie+eng"
        self._embedding_model = None
        self.index_path = index_path
        self.metadata_path = metadata_path
        self._index = None
        self.documents: list[dict[str, Any]] = []
        self._bm25 = None
        self.llm_url = os.getenv("LLM_API_URL", "http://localhost:11434/api/generate")
        self.llm_model = os.getenv("LLM_MODEL", "vinallama:7b-instruct")

    @property
    def bm25(self):
        if self._bm25 is None and self.documents:
            tokenized_corpus = [ViTokenizer.tokenize(doc["content"]).split() for doc in self.documents]
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
            use_transformer = os.getenv("OCR_USE_SENTENCE_TRANSFORMERS", "0") == "1"
            if use_transformer:
                try:
                    from sentence_transformers import SentenceTransformer

                    self._embedding_model = SentenceTransformer(
                        "paraphrase-multilingual-MiniLM-L12-v2",
                        local_files_only=True,
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
                with open(self.metadata_path, "r", encoding="utf-8") as file:
                    self.documents = json.load(file)
            else:
                self._index = faiss.IndexFlatL2(384)
                self.documents = []
        return self._index

    def save_storage(self) -> None:
        import faiss

        if self._index is not None:
            try:
                faiss.write_index(self._index, self.index_path)
                with open(self.metadata_path, "w", encoding="utf-8") as file:
                    json.dump(self.documents, file, ensure_ascii=False, indent=2)
            except (OSError, RuntimeError) as exc:
                logger.warning("ocr_storage_persist_failed: %s", exc)

    def store_embeddings(self, embedded_objects: List[Dict[str, Any]]) -> None:
        if not embedded_objects:
            return

        vectors = np.array([obj["vector"] for obj in embedded_objects]).astype("float32")
        self.index.add(vectors)

        for obj in embedded_objects:
            self.documents.append(
                {
                    "content": obj["content"],
                    "metadata": obj.get("metadata", {}),
                }
            )

        self._refresh_bm25()
        self.save_storage()

    def hybrid_search(self, query: str, top_k: int = 5, alpha: float = 0.5, threshold: float = 0.1) -> List[Dict[str, Any]]:
        if not query:
            return []
        if self.index.ntotal == 0 and not self.documents:
            return []

        keyword_results = []
        if self.bm25:
            tokenized_query = ViTokenizer.tokenize(query).split()
            bm25_scores = self.bm25.get_scores(tokenized_query)
            max_bm25 = np.max(bm25_scores) if len(bm25_scores) > 0 else 0
            normalized_bm25 = bm25_scores / max_bm25 if max_bm25 > 0 else bm25_scores
            top_n_indices = np.argsort(normalized_bm25)[::-1][: top_k * 2]

            for idx in top_n_indices:
                if normalized_bm25[idx] > 0:
                    doc = self.documents[idx].copy()
                    doc["id"] = idx
                    doc["bm25_score"] = float(normalized_bm25[idx])
                    keyword_results.append(doc)

        query_vector = self.embedding_model.encode([query]).astype("float32")
        distances, indices = self.index.search(query_vector, top_k * 2)
        vector_results = []

        if len(distances[0]) > 0:
            max_dist = np.max(distances[0])
            for i, idx in enumerate(indices[0]):
                if idx != -1 and idx < len(self.documents):
                    norm_score = 1 - (distances[0][i] / max_dist) if max_dist > 0 else 1.0
                    doc = self.documents[idx].copy()
                    doc["id"] = idx
                    doc["vector_score"] = float(norm_score)
                    vector_results.append(doc)

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

        final_results = []
        beta = 1.0 - alpha
        for doc_id, data in merged.items():
            final_score = (alpha * data["bm25_score"]) + (beta * data["vector_score"])
            if final_score >= threshold:
                data["id"] = doc_id
                data["final_score"] = round(final_score, 4)
                del data["bm25_score"]
                del data["vector_score"]
                final_results.append(data)

        final_results.sort(key=lambda item: item["final_score"], reverse=True)
        return final_results[:top_k]

    def validate_groundedness(self, query: str, chunks: List[Dict[str, Any]], threshold: float = 0.2) -> Dict[str, Any]:
        del query
        if not chunks:
            return {
                "filtered_chunks": [],
                "should_answer": False,
                "fallback_message": "Khong tim thay thong tin phu hop trong tai lieu.",
            }

        filtered = [chunk for chunk in chunks if chunk.get("final_score", 0) >= threshold]
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
        for index, chunk in enumerate(chunks, start=1):
            metadata = chunk.get("metadata", {})
            page_info = metadata.get("page_label", "")
            context_blocks.append(f"Tai lieu {index} {page_info}:\n{chunk['content']}")
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
        context_text = " ".join(chunk["content"].lower() for chunk in chunks)
        context_tokens = set(ViTokenizer.tokenize(context_text).split())
        overlap = answer_tokens.intersection(context_tokens)
        if len(answer_tokens) > 3 and len(overlap) / len(answer_tokens) < 0.1:
            return False
        return True

    async def get_rag_answer(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        clean_query = self.normalize_text(query)
        context_chunks = self.hybrid_search(clean_query, top_k=top_k)
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
                    json={
                        "model": self.llm_model,
                        "prompt": prompt,
                        "stream": False,
                    },
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
            "sources": [chunk.get("content", "") for chunk in validation["filtered_chunks"]],
            "source_chunks": validation["filtered_chunks"],
            "grounded": is_valid,
        }

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not query or self.index.ntotal == 0:
            return []

        query_vector = self.embedding_model.encode([query]).astype("float32")
        distances, indices = self.index.search(query_vector, top_k)
        results = []

        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.documents):
                doc = self.documents[idx].copy()
                doc["score"] = float(distances[0][i])
                results.append(doc)

        return results

    def repair_text_encoding(self, text: str) -> str:
        repaired = text.translate(self.TCVN3_CHAR_MAP)
        for source, target in self.COMMON_VNI_REPLACEMENTS:
            repaired = repaired.replace(source, target).replace(source.upper(), target.upper())

        for codec in ("latin1", "cp1252"):
            try:
                candidate = repaired.encode(codec).decode("utf-8")
                if self._vietnamese_score(candidate) > self._vietnamese_score(repaired):
                    repaired = candidate
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        return repaired

    def normalize_text(self, text: str) -> str:
        if not text:
            return ""

        text = self.repair_text_encoding(text)
        text = unicodedata.normalize("NFC", text)
        text = text.replace("\x0c", "\n")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in ["\n", "\t"])
        text = self._normalize_bullets(text)
        text = self._strip_administrative_noise(text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def chunk_text(self, text: str, page_number: int | None = None, page_label: str | None = None) -> list[dict[str, Any]]:
        if not text:
            return []

        article_matches = list(self.ARTICLE_PATTERN.finditer(text))
        if not article_matches:
            return [
                {
                    "content": text,
                    "metadata": {
                        "dieu": None,
                        "khoan": None,
                        "page_number": page_number,
                        "page_label": page_label or self._format_page_label(page_number),
                    },
                }
            ]

        chunks: list[dict[str, Any]] = []
        for index, match in enumerate(article_matches):
            start = match.start()
            end = article_matches[index + 1].start() if index + 1 < len(article_matches) else len(text)
            article_content = text[start:end].strip()
            article_header = match.group(0).strip()
            article_number_match = re.search(r"\d+", article_header)
            article_number = article_number_match.group(0) if article_number_match else None

            clause_pattern = re.compile(
                r"^\s*(Khoản\s+\d+[:.]?|Khoan\s+\d+[:.]?|\(?\d+\)[\s.]|\d+\.)",
                re.IGNORECASE | re.MULTILINE,
            )
            clause_matches = list(clause_pattern.finditer(article_content))
            if not clause_matches:
                chunks.append(
                    {
                        "content": article_content,
                        "metadata": {
                            "dieu": article_number,
                            "khoan": None,
                            "page_number": page_number,
                            "page_label": page_label or self._format_page_label(page_number),
                        },
                    }
                )
                continue

            for clause_index, clause_match in enumerate(clause_matches):
                clause_start = clause_match.start()
                clause_end = clause_matches[clause_index + 1].start() if clause_index + 1 < len(clause_matches) else len(article_content)
                clause_text = article_content[clause_start:clause_end].strip()
                clause_number_match = re.search(r"\d+", clause_match.group(0))
                clause_number = clause_number_match.group(0) if clause_number_match else None
                chunks.append(
                    {
                        "content": f"{article_header}\n{clause_text}",
                        "metadata": {
                            "dieu": article_number,
                            "khoan": clause_number,
                            "page_number": page_number,
                            "page_label": page_label or self._format_page_label(page_number),
                        },
                    }
                )
        return chunks

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        contents = [chunk["content"] for chunk in chunks]
        vectors = self.embedding_model.encode(contents)
        result = []
        for index, chunk in enumerate(chunks):
            result.append(
                {
                    "content": chunk["content"],
                    "vector": vectors[index].tolist(),
                    "metadata": chunk.get("metadata", {}),
                }
            )
        return result

    def preprocess_image_for_ocr(self, image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        enhanced = ImageEnhance.Contrast(grayscale).enhance(1.8)
        sharpened = enhanced.filter(ImageFilter.SHARPEN)
        return sharpened

    def extract_from_image(self, image_bytes: bytes) -> str:
        image = Image.open(io.BytesIO(image_bytes))
        processed = self.preprocess_image_for_ocr(image)
        text = pytesseract.image_to_string(processed, lang=self.lang, config=self.config)
        return text.strip()

    def extract_pages_from_pdf(self, pdf_bytes: bytes) -> list[dict[str, Any]]:
        pages = self._extract_pdf_text_pages(pdf_bytes)
        if any(page["text"].strip() for page in pages):
            return pages

        images = convert_from_bytes(pdf_bytes)
        return [
            {
                "page_number": index + 1,
                "text": pytesseract.image_to_string(
                    self.preprocess_image_for_ocr(image),
                    lang=self.lang,
                    config=self.config,
                ).strip(),
            }
            for index, image in enumerate(images)
        ]

    def extract_from_pdf(self, pdf_bytes: bytes) -> str:
        pages = self.extract_pages_from_pdf(pdf_bytes)
        cleaned_pages = self.clean_pages(pages)
        return "\n\n".join(f"--- Page {page['page_number']} ---\n{page['text']}" for page in cleaned_pages if page["text"])

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

        normalized_pages = []
        for index, lines in enumerate(pages, start=1):
            normalized_pages.append({"page_number": index, "text": "\n".join(lines).strip()})
        return normalized_pages or [{"page_number": 1, "text": ""}]

    def extract_from_docx(self, docx_bytes: bytes) -> str:
        pages = self.clean_pages(self.extract_pages_from_docx(docx_bytes))
        return "\n\n".join(f"--- Page {page['page_number']} ---\n{page['text']}" for page in pages if page["text"])

    def extract_pages_from_txt(self, file_bytes: bytes) -> list[dict[str, Any]]:
        raw_text = file_bytes.decode("utf-8", errors="ignore")
        parts = [part.strip() for part in raw_text.replace("\r\n", "\n").split("\f")]
        pages = [{"page_number": index + 1, "text": part} for index, part in enumerate(parts) if part]
        return pages or [{"page_number": 1, "text": raw_text.strip()}]

    def extract_from_txt(self, file_bytes: bytes) -> str:
        pages = self.clean_pages(self.extract_pages_from_txt(file_bytes))
        return "\n\n".join(f"--- Page {page['page_number']} ---\n{page['text']}" for page in pages if page["text"])

    def clean_pages(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_pages = []
        for page in pages:
            lines = [self.normalize_text(line) for line in page.get("text", "").splitlines()]
            lines = [line for line in lines if line and not self.PAGE_ONLY_PATTERN.match(line)]
            normalized_pages.append({"page_number": page["page_number"], "text": "\n".join(lines).strip()})

        first_line_counts = Counter()
        last_line_counts = Counter()
        for page in normalized_pages:
            lines = [line.strip() for line in page["text"].splitlines() if line.strip()]
            if lines:
                first_line_counts[lines[0]] += 1
                last_line_counts[lines[-1]] += 1

        repeated_headers = {line for line, count in first_line_counts.items() if count >= 2 and len(line) <= 120}
        repeated_footers = {line for line, count in last_line_counts.items() if count >= 2 and len(line) <= 120}

        cleaned_pages = []
        for page in normalized_pages:
            lines = [line.strip() for line in page["text"].splitlines() if line.strip()]
            if lines and lines[0] in repeated_headers:
                lines = lines[1:]
            if lines and lines[-1] in repeated_footers:
                lines = lines[:-1]
            cleaned_pages.append({"page_number": page["page_number"], "text": "\n".join(lines).strip()})
        return cleaned_pages

    def build_page_index(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        page_index = []
        for page in pages:
            text = page.get("text", "")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            heading = lines[0] if lines else ""
            page_index.append(
                {
                    "page_number": page["page_number"],
                    "heading": heading[:160],
                    "preview": text[:240],
                    "line_count": len(lines),
                }
            )
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
        first_non_empty_line = next((line.strip() for line in lowered.splitlines() if line.strip()), "")
        scores: dict[str, int] = {}
        matched_signals: dict[str, list[str]] = {}

        for doc_type, keywords in self.DOCUMENT_PATTERNS.items():
            matches = [keyword for keyword in keywords if keyword in lowered]
            scores[doc_type] = len(matches)
            matched_signals[doc_type] = matches
            if any(first_non_empty_line.startswith(keyword) for keyword in keywords):
                scores[doc_type] += 2

        if self.ARTICLE_PATTERN.search(text):
            scores["quyet_dinh"] = scores.get("quyet_dinh", 0) + 1
            scores["nghi_dinh"] = scores.get("nghi_dinh", 0) + 1

        best_type = max(scores, key=scores.get) if scores else "khac"
        best_score = scores.get(best_type, 0)
        total_signal_count = sum(scores.values()) or 1
        confidence = round(best_score / total_signal_count, 2) if best_score else 0.0

        return {
            "document_type": best_type if best_score else "khac",
            "confidence": confidence,
            "matched_signals": matched_signals.get(best_type, []),
        }

    def process_document(self, file_bytes: bytes, filename: str) -> dict[str, Any]:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        pages = self._extract_pages(file_bytes, ext)
        cleaned_pages = self.clean_pages(pages)
        clean_body_text = "\n\n".join(page["text"] for page in cleaned_pages if page["text"]).strip()
        clean_text = "\n\n".join(
            f"--- Page {page['page_number']} ---\n{page['text']}" if len(cleaned_pages) > 1 else page["text"]
            for page in cleaned_pages
            if page["text"]
        ).strip()

        chunks: list[dict[str, Any]] = []
        for page in cleaned_pages:
            page_chunks = self.chunk_text(
                page["text"],
                page_number=page["page_number"],
                page_label=self._format_page_label(page["page_number"]),
            )
            chunks.extend(page_chunks)

        classification = self.classify_document(clean_body_text)
        structure = self.detect_document_structure(clean_body_text)

        return {
            "filename": filename,
            "extension": ext,
            "pages": cleaned_pages,
            "page_count": len(cleaned_pages),
            "page_index": self.build_page_index(cleaned_pages),
            "raw_text": "\n\n".join(page.get("text", "") for page in pages).strip(),
            "clean_text": clean_text,
            "chunks": chunks,
            "classification": classification,
            "structure": structure,
            "supported_formats": ["pdf", "docx", "txt", "jpg", "jpeg", "png", "bmp", "tif", "tiff"],
        }

    def process_file(self, file_bytes: bytes, filename: str) -> str:
        return self.process_document(file_bytes, filename)["clean_text"]

    def _extract_pages(self, file_bytes: bytes, ext: str) -> list[dict[str, Any]]:
        if ext == "pdf":
            return self.extract_pages_from_pdf(file_bytes)
        if ext == "docx":
            return self.extract_pages_from_docx(file_bytes)
        if ext == "txt":
            return self.extract_pages_from_txt(file_bytes)
        if ext in ["jpg", "jpeg", "png", "bmp", "tif", "tiff"]:
            return [{"page_number": 1, "text": self.extract_from_image(file_bytes)}]
        raise ValueError(f"Unsupported file format: {ext}")

    def _extract_pdf_text_pages(self, pdf_bytes: bytes) -> list[dict[str, Any]]:
        try:
            from pypdf import PdfReader
        except Exception:
            return [{"page_number": 1, "text": ""}]

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            pages.append({"page_number": index, "text": page_text})
        return pages or [{"page_number": 1, "text": ""}]

    def _normalize_bullets(self, text: str) -> str:
        text = re.sub(r"^[•●▪■]+", "-", text, flags=re.MULTILINE)
        text = re.sub(r"[“”]", '"', text)
        text = re.sub(r"[‘’]", "'", text)
        return text

    def _strip_administrative_noise(self, text: str) -> str:
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                lines.append("")
                continue
            if self.PAGE_ONLY_PATTERN.match(stripped):
                continue
            if re.fullmatch(r"[_\-=\s]{3,}", stripped):
                continue
            lines.append(stripped)
        return "\n".join(lines)

    def _vietnamese_score(self, text: str) -> int:
        return len(re.findall(r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệóòỏõọốồổỗộớờởỡợíìỉĩịúùủũụứừửữựýỳỷỹỵ]", text.lower()))

    def _ascii_fold(self, text: str) -> str:
        normalized = unicodedata.normalize("NFD", text)
        stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return stripped.replace("đ", "d").replace("Đ", "D").lower()

    def _first_match(self, pattern: re.Pattern[str], text: str) -> str | None:
        match = pattern.search(text)
        if not match:
            return None
        value = match.group(1).strip()
        return value[:250] if value else None

    def _format_page_label(self, page_number: int | None) -> str:
        return f"(Trang {page_number})" if page_number else ""
