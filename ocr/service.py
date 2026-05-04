import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
import io
import unicodedata
import re
import os
import json
import numpy as np
import httpx
from typing import List, Dict, Any, Optional
from pyvi import ViTokenizer

class OCRService:
    def __init__(self, index_path: str = "ocr_vectors.index", metadata_path: str = "ocr_metadata.json"):
        # Tesseract configuration for Vietnamese support
        # Note: 'vie' must be installed on the system tesseract-ocr
        self.config = '--oem 3 --psm 6'
        self.lang = 'vie+eng'
        self._embedding_model = None
        
        # Vector Storage configuration
        self.index_path = index_path
        self.metadata_path = metadata_path
        self._index = None
        self.documents = []  # List of {"content": "...", "metadata": {...}}
        self._bm25 = None    # BM25 object for keyword search

        # RAG Config (Example: using Ollama local LLM)
        self.llm_url = os.getenv("LLM_API_URL", "http://localhost:11434/api/generate")
        self.llm_model = os.getenv("LLM_MODEL", "vinallama:7b-instruct") # Or llama3, etc.

    @property
    def bm25(self):
        """Lazy load or initialize BM25 index."""
        if self._bm25 is None and self.documents:
            from rank_bm25 import BM25Okapi
            # Tokenize all documents for BM25
            tokenized_corpus = [ViTokenizer.tokenize(doc["content"]).split() for doc in self.documents]
            self._bm25 = BM25Okapi(tokenized_corpus)
        return self._bm25

    def _refresh_bm25(self):
        """Reset BM25 to force re-indexing on next access."""
        self._bm25 = None

    @property
    def embedding_model(self):
        """Lazy load embedding model to save memory if not used."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                # Using a multilingual model that works well for Vietnamese
                # 'paraphrase-multilingual-MiniLM-L12-v2' is a good balance of speed/quality
                self._embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            except ImportError:
                raise ImportError("Please install 'sentence-transformers' to use embedding features.")
        return self._embedding_model

    @property
    def index(self):
        """Lazy load or initialize FAISS index."""
        if self._index is None:
            import faiss
            if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
                self._index = faiss.read_index(self.index_path)
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    self.documents = json.load(f)
            else:
                # Initialize an L2 index (Euclidean distance)
                # We'll use 384 dimensions for paraphrase-multilingual-MiniLM-L12-v2
                self._index = faiss.IndexFlatL2(384)
                self.documents = []
        return self._index

    def save_storage(self):
        """Persist FAISS index and metadata to disk."""
        import faiss
        if self._index is not None:
            faiss.write_index(self._index, self.index_path)
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)

    def store_embeddings(self, embedded_objects: List[Dict[str, Any]]):
        """
        Store embedding objects into the vector database.
        Input: [{"content": "...", "vector": [...], "metadata": {...}}, ...]
        """
        if not embedded_objects:
            return

        vectors = np.array([obj["vector"] for obj in embedded_objects]).astype('float32')
        
        # Add to FAISS index
        self.index.add(vectors)
        
        # Store metadata and content
        for obj in embedded_objects:
            self.documents.append({
                "content": obj["content"],
                "metadata": obj.get("metadata", {})
            })
        
        self._refresh_bm25()
        self.save_storage()

    def hybrid_search(self, query: str, top_k: int = 5, alpha: float = 0.5, threshold: float = 0.1) -> List[Dict[str, Any]]:
        """
        Perform hybrid search with weight combining, normalization and deduplication.
        Formula: final_score = alpha * bm25_score + (1 - alpha) * vector_score
        """
        if not query:
            return []

        # 1. Get Keyword (BM25) results
        keyword_results = []
        if self.bm25:
            tokenized_query = ViTokenizer.tokenize(query).split()
            bm25_scores = self.bm25.get_scores(tokenized_query)
            
            # Normalize BM25 scores to [0, 1]
            max_bm25 = np.max(bm25_scores) if len(bm25_scores) > 0 else 0
            if max_bm25 > 0:
                normalized_bm25 = bm25_scores / max_bm25
            else:
                normalized_bm25 = bm25_scores

            # Filter top_k candidate indices
            top_n_indices = np.argsort(normalized_bm25)[::-1][:top_k * 2] # Get more candidates for merging
            for idx in top_n_indices:
                if normalized_bm25[idx] > 0:
                    doc = self.documents[idx].copy()
                    doc["id"] = idx # Unique identifier for deduplication
                    doc["bm25_score"] = float(normalized_bm25[idx])
                    keyword_results.append(doc)

        # 2. Get Vector search results
        # Note: Vector search (L2) returns distance. Smaller is better.
        # We need to convert it to a similarity score [0, 1] where larger is better.
        query_vector = self.embedding_model.encode([query]).astype('float32')
        distances, indices = self.index.search(query_vector, top_k * 2)
        
        vector_results = []
        if len(distances[0]) > 0:
            max_dist = np.max(distances[0])
            min_dist = np.min(distances[0])
            dist_range = max_dist - min_dist
            
            for i, idx in enumerate(indices[0]):
                if idx != -1 and idx < len(self.documents):
                    # Simple conversion: 1 - (normalized distance)
                    # This is a rough estimation. In production, Cosine similarity is preferred for this.
                    norm_score = 1 - (distances[0][i] / max_dist) if max_dist > 0 else 1.0
                    
                    doc = self.documents[idx].copy()
                    doc["id"] = idx
                    doc["vector_score"] = float(norm_score)
                    vector_results.append(doc)

        # 3. Merge and Deduplicate
        merged = {}
        # Union of results
        for doc in keyword_results:
            merged[doc["id"]] = {
                "content": doc["content"],
                "metadata": doc["metadata"],
                "bm25_score": doc["bm25_score"],
                "vector_score": 0.0
            }
            
        for doc in vector_results:
            if doc["id"] in merged:
                merged[doc["id"]]["vector_score"] = doc["vector_score"]
            else:
                merged[doc["id"]] = {
                    "content": doc["content"],
                    "metadata": doc["metadata"],
                    "bm25_score": 0.0,
                    "vector_score": doc["vector_score"]
                }

        # 4. Combine Scores and Filter
        final_results = []
        beta = 1.0 - alpha
        for doc_id, data in merged.items():
            final_score = (alpha * data["bm25_score"]) + (beta * data["vector_score"])
            
            if final_score >= threshold:
                data["final_score"] = round(final_score, 4)
                # Remove intermediate scores from output
                del data["bm25_score"]
                del data["vector_score"]
                final_results.append(data)

        # 5. Sort and return Top K
        final_results.sort(key=lambda x: x["final_score"], reverse=True)
        return final_results[:top_k]

    def validate_groundedness(self, query: str, chunks: List[Dict[str, Any]], threshold: float = 0.2) -> Dict[str, Any]:
        """
        Validate relevance of retrieved chunks to prevent hallucination.
        """
        if not chunks:
            return {
                "filtered_chunks": [],
                "should_answer": False,
                "fallback_message": "Không tìm thấy thông tin phù hợp trong tài liệu."
            }

        # 1. Threshold Filtering (The hybrid search already has a threshold, but this is a secondary check)
        filtered = [c for c in chunks if c.get("final_score", 0) >= threshold]
        
        # 2. Context Validation
        if not filtered:
            return {
                "filtered_chunks": [],
                "should_answer": False,
                "fallback_message": "Dữ liệu tìm thấy không đủ tin cậy để trả lời."
            }
            
        # 3. Decision Logic (e.g. top score must be high enough)
        top_score = filtered[0].get("final_score", 0)
        if top_score < threshold:
             return {
                "filtered_chunks": filtered,
                "should_answer": False,
                "fallback_message": "Nội dung tìm thấy không chứa câu trả lời chính xác."
            }

        return {
            "filtered_chunks": filtered[:3], # Top 3
            "should_answer": True,
            "fallback_message": None
        }

    def build_grounded_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """
        Build a strict grounded prompt.
        """
        context_text = "\n\n".join([f"Tài liệu {i+1}:\n{c['content']}" for i, c in enumerate(chunks)])
        
        return f"""BẠN LÀ TRỢ LÝ PHÁP LUẬT CHUYÊN NGHIỆP.

YÊU CẦU BẮT BUỘC:
1. CHỈ sử dụng thông tin từ phần 'Context' dưới đây.
2. Nếu không tìm thấy thông tin chính xác, hãy trả lời: "Không tìm thấy thông tin phù hợp trong tài liệu".
3. KHÔNG tự ý suy luận hoặc sử dụng kiến thức bên ngoài.
4. KHÔNG viết sai nội dung pháp lý. Nếu nội dung có Điều/Khoản, phải dẫn chiếu đúng.

CONTEXT:
{context_text}

CÂU HỎI:
{query}

TRẢ LỜI:"""

    def validate_answer_vs_context(self, answer: str, chunks: List[Dict[str, Any]]) -> bool:
        """
        Check if the generated answer has minimal overlap with context keywords.
        """
        if "Không tìm thấy thông tin" in answer:
            return True
            
        # Simple keyword overlap check
        answer_tokens = set(ViTokenizer.tokenize(answer.lower()).split())
        
        # Filter out short/common tokens if needed
        context_text = " ".join([c["content"].lower() for c in chunks])
        context_tokens = set(ViTokenizer.tokenize(context_text).split())
        
        overlap = answer_tokens.intersection(context_tokens)
        # If less than 10% of answer words are in context, it might be hallucination
        if len(answer_tokens) > 3 and len(overlap) / len(answer_tokens) < 0.1:
            return False
        return True

    async def get_rag_answer(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """
        Generate a RAG answer based on retrieved context with Groundedness check.
        """
        # 1. Normalize Query
        clean_query = self.normalize_text(query)
        
        # 2. Hybrid Search
        context_chunks = self.hybrid_search(clean_query, top_k=top_k)
        
        # 3. Groundedness Validation
        val_result = self.validate_groundedness(clean_query, context_chunks)
        
        if not val_result["should_answer"]:
            return {
                "answer": val_result["fallback_message"],
                "sources": [],
                "grounded": False
            }

        # 4. Build Prompt
        prompt = self.build_grounded_prompt(clean_query, val_result["filtered_chunks"])
        
        # 5. Call LLM (Asynchronous call)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.llm_url,
                    json={
                        "model": self.llm_model,
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                llm_output = response.json().get("response", "").strip()
        except Exception as e:
            llm_output = f"Lỗi khi kết nối với mô hình AI: {str(e)}"
            
        # 6. Post-validation (Self-Correction)
        is_valid = self.validate_answer_vs_context(llm_output, val_result["filtered_chunks"])
        if not is_valid:
            llm_output = "Xin lỗi, tôi không thể tìm thấy câu trả lời chính xác trong tài liệu này mặc dù có dữ liệu liên quan."

        return {
            "answer": llm_output,
            "sources": [c.get("content", "") for c in val_result["filtered_chunks"]],
            "grounded": is_valid
        }

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for the most similar chunks based on a query.
        """
        if not query or self.index.ntotal == 0:
            return []

        # Generate query embedding
        query_vector = self.embedding_model.encode([query]).astype('float32')
        
        # Search in FAISS
        distances, indices = self.index.search(query_vector, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.documents):
                doc = self.documents[idx].copy()
                doc["score"] = float(distances[0][i])
                results.append(doc)
                
        return results

    def normalize_text(self, text: str) -> str:
        """
        Clean and normalize OCR text:
        1. Normalize Unicode (NFC)
        2. Remove non-printable and garbage characters
        3. Replace multiple spaces with 1 space
        4. Replace multiple newlines with 1 newline
        5. Trim whitespace
        """
        if not text:
            return ""

        # 1. Normalize Unicode (NFC)
        text = unicodedata.normalize('NFC', text)

        # 2. Remove non-printable characters and garbage from OCR (like , \x0c)
        # Keep basic punctuation, alphanumeric, and common symbols
        # \x0c is common in OCR as form feed (page breaks)
        text = text.replace('\x0c', '')
        
        # Remove other non-printable chars except space and newline
        text = "".join(ch for ch in text if unicodedata.category(ch)[0] != 'C' or ch in ['\n', '\r', '\t'])

        # 3. Standardize spaces
        text = re.sub(r'[ \t]+', ' ', text)
        
        # 4. Handle multiple newlines and spaces around them
        # Replace multiple newlines (with optional spaces/tabs) with 1 newline
        text = re.sub(r'\s*\n\s*', '\n', text)
        text = re.sub(r'\n+', '\n', text)

        # 5. Trim
        text = text.strip()

        return text

    def chunk_text(self, text: str) -> list:
        """
        Split normalized text into chunks based on legal structure (Điều, Khoản).
        """
        if not text:
            return []

        # Regex for "Điều X." or "ĐIỀU X:" etc. (Case insensitive, flexible punctuation)
        # Matches "Điều 1", "Điều 1.", "Điều 1 :", "ĐIỀU 1"
        dieu_pattern = re.compile(r'^(Điều\s+\d+[:.]?|ĐIỀU\s+\d+[:.]?)', re.IGNORECASE | re.MULTILINE)
        
        # Find all split points for "Điều"
        dieu_matches = list(dieu_pattern.finditer(text))
        
        if not dieu_matches:
            # If no "Điều" found, treat the whole text as one chunk without metadata
            return [{"content": text, "metadata": {"dieu": None, "khoan": None}}]

        chunks = []
        for i, match in enumerate(dieu_matches):
            start = match.start()
            end = dieu_matches[i+1].start() if i + 1 < len(dieu_matches) else len(text)
            
            dieu_content = text[start:end].strip()
            dieu_header = match.group(1)
            # Extract number from "Điều 1"
            dieu_num_match = re.search(r'\d+', dieu_header)
            dieu_num = dieu_num_match.group() if dieu_num_match else dieu_header

            # Within this "Điều", find "Khoản X."
            # Matches "1. ", "2. ", "Khoản 1.", "1) ", "(1) "
            # We prioritize explicit "1. ", "2. " at beginning of line within the Điều content
            khoan_pattern = re.compile(r'^\s*(\d+[\.)]|Khoản\s+\d+[\.)]?)', re.MULTILINE)
            khoan_matches = list(khoan_pattern.finditer(dieu_content))
            
            if not khoan_matches:
                # No sub-clauses, return entire Điều as one chunk
                chunks.append({
                    "content": dieu_content,
                    "metadata": {"dieu": dieu_num, "khoan": None}
                })
            else:
                # Extract text before first Khoản (the heading/intro of the Điều)
                intro_text = dieu_content[:khoan_matches[0].start()].strip()
                
                # If intro_text is more than just the header, we might want to keep it or prepend to first Khoản
                # For simplicity, if there are Khoảns, we split everything into Khoảns.
                # If there's intro text, we can prepend it to each Khoản chunk to keep context
                
                for j, k_match in enumerate(khoan_matches):
                    k_start = k_match.start()
                    k_end = khoan_matches[j+1].start() if j + 1 < len(khoan_matches) else len(dieu_content)
                    
                    khoan_text = dieu_content[k_start:k_end].strip()
                    khoan_header = k_match.group(1)
                    khoan_num_match = re.search(r'\d+', khoan_header)
                    khoan_num = khoan_num_match.group() if khoan_num_match else khoan_header
                    
                    # Optionally prepend Điều header to each Khoản for context
                    full_content = f"{dieu_header}\n{khoan_text}"
                    
                    chunks.append({
                        "content": full_content,
                        "metadata": {"dieu": dieu_num, "khoan": khoan_num}
                    })

        return chunks

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert a list of chunks into embedding objects.
        Input format: [{"content": "...", "metadata": {...}}, ...]
        Output format: [{"content": "...", "vector": [...], "metadata": {...}}, ...]
        """
        if not chunks:
            return []

        # Extract only the content strings for batch processing
        contents = [chunk["content"] for chunk in chunks]
        
        # Generate embeddings in batch
        vectors = self.embedding_model.encode(contents)
        
        # Combine back into objects
        result = []
        for i, chunk in enumerate(chunks):
            result.append({
                "content": chunk["content"],
                "vector": vectors[i].tolist(), # Convert numpy array to list
                "metadata": chunk.get("metadata", {})
            })
            
        return result

    def extract_from_image(self, image_bytes: bytes) -> str:
        """
        Extract text from an image.
        """
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang=self.lang, config=self.config)
        return text.strip()

    def extract_from_pdf(self, pdf_bytes: bytes) -> str:
        """
        Extract text from a multi-page PDF by converting each page to an image.
        """
        images = convert_from_bytes(pdf_bytes)
        full_text = []
        
        for i, image in enumerate(images):
            text = pytesseract.image_to_string(image, lang=self.lang, config=self.config)
            full_text.append(f"--- Page {i+1} ---\n{self.normalize_text(text)}")
            
        return "\n\n".join(full_text)

    def process_file(self, file_bytes: bytes, filename: str) -> str:
        """
        Identify file type and process accordingly.
        """
        ext = filename.split('.')[-1].lower()
        if ext == 'pdf':
            return self.extract_from_pdf(file_bytes)
        elif ext in ['jpg', 'jpeg', 'png', 'bmp']:
            raw_text = self.extract_from_image(file_bytes)
            return self.normalize_text(raw_text)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
