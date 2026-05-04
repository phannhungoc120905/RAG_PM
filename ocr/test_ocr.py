
import unittest
from ocr.service import OCRService
import unicodedata
import os
import asyncio
from unittest.mock import AsyncMock, patch

class TestOCR(unittest.TestCase):
    def setUp(self):
        # Use temporary files for testing vector storage
        self.test_index = "test_ocr.index"
        self.test_metadata = "test_metadata.json"
        self.ocr_service = OCRService(index_path=self.test_index, metadata_path=self.test_metadata)

    def tearDown(self):
        # Clean up test files
        if os.path.exists(self.test_index):
            os.remove(self.test_index)
        if os.path.exists(self.test_metadata):
            os.remove(self.test_metadata)

    def test_rag_answer_mock(self):
        """Test RAG answer generation with mocked LLM response"""
        chunks = [
            {"content": "Điều 1. Quy định về lao động.", "metadata": {"dieu": "1"}}
        ]
        embedded = self.ocr_service.embed_chunks(chunks)
        self.ocr_service.store_embeddings(embedded)

        # Mock successful LLM response using a custom mock that behaves correctly when awaited
        class MockResponse:
            def __init__(self):
                self.status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {"response": "Theo Điều 1, đây là quy định về lao động."}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MockResponse()
            
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(self.ocr_service.get_rag_answer("lao động là gì"))
            
            self.assertEqual(result["answer"], "Theo Điều 1, đây là quy định về lao động.")
            self.assertIn("Điều 1. Quy định về lao động.", result["sources"][0])

    def test_rag_no_info(self):
        """Test RAG behavior when no info is found"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.ocr_service.get_rag_answer("thông tin không tồn tại"))
        # Match the new fallback message from validate_groundedness
        self.assertEqual(result["answer"], "Không tìm thấy thông tin phù hợp trong tài liệu.")
        self.assertEqual(len(result["sources"]), 0)

    def test_vector_storage_and_search(self):
        """Test storing embeddings and performing a search"""
        # 1. Prepare data
        chunks = [
            {"content": "Công dân có quyền tự do ngôn luận.", "metadata": {"dieu": "25"}},
            {"content": "Mọi người đều bình đẳng trước pháp luật.", "metadata": {"dieu": "16"}}
        ]
        embedded = self.ocr_service.embed_chunks(chunks)
        
        # 2. Store
        self.ocr_service.store_embeddings(embedded)
        
        # 3. Verify persistence (re-init service)
        new_service = OCRService(index_path=self.test_index, metadata_path=self.test_metadata)
        self.assertEqual(new_service.index.ntotal, 2)
        
        # 4. Search
        results = new_service.search("quyền tự do", top_k=1)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["metadata"]["dieu"], "25")
        self.assertIn("score", results[0])

    def test_hybrid_search(self):
        """Test hybrid search with ranking, merging and thresholding"""
        chunks = [
            {"content": "Công dân có quyền tự do ngôn luận.", "metadata": {"dieu": "25"}},
            {"content": "Mọi người đều bình đẳng trước pháp luật.", "metadata": {"dieu": "16"}},
            {"content": "Hợp đồng kinh tế có hiệu lực từ ngày ký.", "metadata": {"dieu": "100"}}
        ]
        embedded = self.ocr_service.embed_chunks(chunks)
        self.ocr_service.store_embeddings(embedded)
        
        # Search with threshold and alpha
        results = self.ocr_service.hybrid_search("ngôn luận", top_k=5, alpha=0.5, threshold=0.1)
        
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        # Check sort order
        if len(results) > 1:
            self.assertGreaterEqual(results[0]["final_score"], results[1]["final_score"])
        
        # Check metadata preserved
        self.assertIn("metadata", results[0])
        self.assertIn("final_score", results[0])

    def test_hybrid_search_threshold(self):
        """Test that threshold excludes irrelevant results"""
        chunks = [
            {"content": "Văn bản về luật lao động.", "metadata": {"type": "law"}}
        ]
        embedded = self.ocr_service.embed_chunks(chunks)
        self.ocr_service.store_embeddings(embedded)
        
        # Search for something completely different with high threshold
        results = self.ocr_service.hybrid_search("nấu ăn ngon", top_k=5, threshold=0.9)
        self.assertEqual(len(results), 0)

    def test_normalize_unicode(self):
        """Test Unicode normalization (NFC)"""
        # "Tiếng Việt" with combined characters (NFD)
        nfd_text = "Tiếng Việt" # This might be NFD in some editors
        normalized = self.ocr_service.normalize_text(nfd_text)
        self.assertEqual(unicodedata.normalize('NFC', normalized), normalized)

    def test_remove_garbage_chars(self):
        """Test removal of non-printable and OCR garbage characters"""
        input_text = "Hello\x0cWorld! \u0000"
        expected = "HelloWorld!"
        self.assertEqual(self.ocr_service.normalize_text(input_text), expected)

    def test_normalize_whitespace(self):
        """Test multiple spaces and newlines normalization"""
        input_text = "  Word1    Word2  \n\n\nWord3 \t Word4  "
        # Since I implemented r'\n\s*\n+' -> '\n', it should be 1 newline
        # Actually requirements said replace multiple newlines -> 1 newline
        expected = "Word1 Word2\nWord3 Word4"
        self.assertEqual(self.ocr_service.normalize_text(input_text), expected)

    def test_trim_text(self):
        """Test trimming of text"""
        input_text = "   Leading and trailing spaces   "
        expected = "Leading and trailing spaces"
        self.assertEqual(self.ocr_service.normalize_text(input_text), expected)

    def test_preserve_casing(self):
        """Test that casing is preserved (important for legal docs)"""
        input_text = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM"
        result = self.ocr_service.normalize_text(input_text)
        self.assertEqual(result, input_text)

    def test_unsupported_format(self):
        with self.assertRaises(ValueError):
            self.ocr_service.process_file(b"dummy", "test.txt")

    def test_preserve_legal_structure(self):
        """Test and preserve structure like Articles/Sections (important for legal docs)"""
        input_text = "Điều 1. Phạm vi điều chỉnh\n\nQuy định này quy định về...\n\nĐiều 2. Đối tượng áp dụng"
        expected = "Điều 1. Phạm vi điều chỉnh\nQuy định này quy định về...\nĐiều 2. Đối tượng áp dụng"
        self.assertEqual(self.ocr_service.normalize_text(input_text), expected)

    def test_preserve_punctuation(self):
        """Test that important punctuation is not removed"""
        input_text = "Hợp đồng (số 123/2024/HĐKT); Ngày: 04/05/2026. Hết!"
        expected = "Hợp đồng (số 123/2024/HĐKT); Ngày: 04/05/2026. Hết!"
        self.assertEqual(self.ocr_service.normalize_text(input_text), expected)

    def test_broken_lines(self):
        """Test handling lines broken by OCR with unnecessary newlines/spaces"""
        input_text = "Cộng hòa xã   \n hội chủ nghĩa \n Việt Nam"
        expected = "Cộng hòa xã\nhội chủ nghĩa\nViệt Nam"
        # Current logic replaces \n\s*\n with \n, but single \n is kept and trimmed by \s*\n\s*
        self.assertEqual(self.ocr_service.normalize_text(input_text), expected)

    def test_empty(self):
        """Test empty input or whitespace-only input"""
        self.assertEqual(self.ocr_service.normalize_text(""), "")
        self.assertEqual(self.ocr_service.normalize_text("   \n   "), "")

    def test_unicode_strict(self):
        """Test strict Unicode characters (Vietnamese markers)"""
        input_text = "Tiếng Việt có dấu: ă, ắ, ằ, ẳ, ẵ, ặ, đ, ơ, ờ, ở, ở, ỡ, ợ, ư, ừ, ử, ữ, ự"
        nfc_expected = unicodedata.normalize('NFC', input_text)
        result = self.ocr_service.normalize_text(input_text)
        self.assertEqual(result, nfc_expected)

    def test_chunk_basic(self):
        """Test basic chunking by Điều"""
        input_text = "Điều 1. Nội dung 1\nĐiều 2. Nội dung 2"
        chunks = self.ocr_service.chunk_text(input_text)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["metadata"]["dieu"], "1")
        self.assertEqual(chunks[1]["metadata"]["dieu"], "2")

    def test_chunk_with_khoan(self):
        """Test chunking with Khoản within a Điều"""
        input_text = "Điều 1. Tổng quát\n1. Khoản một\n2. Khoản hai\nĐiều 2. Chi tiết"
        chunks = self.ocr_service.chunk_text(input_text)
        # Should be 3 chunks: Điều 1-Khoản 1, Điều 1-Khoản 2, Điều 2
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0]["metadata"]["dieu"], "1")
        self.assertEqual(chunks[0]["metadata"]["khoan"], "1")
        self.assertEqual(chunks[1]["metadata"]["khoan"], "2")
        self.assertEqual(chunks[2]["metadata"]["dieu"], "2")
        self.assertIsNone(chunks[2]["metadata"]["khoan"])

    def test_chunk_flexible_format(self):
        """Test chunking with flexible formats like ĐIỀU 1, Điều 1:"""
        input_text = "ĐIỀU 1: Tiêu đề\nNội dung\nĐiều 2. Tiếp theo"
        chunks = self.ocr_service.chunk_text(input_text)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["metadata"]["dieu"], "1")
        self.assertEqual(chunks[1]["metadata"]["dieu"], "2")

    def test_chunk_no_structure(self):
        """Test chunking when no Điều is found"""
        input_text = "Đoạn văn tự do không theo cấu trúc luật."
        chunks = self.ocr_service.chunk_text(input_text)
        self.assertEqual(len(chunks), 1)
        self.assertIsNone(chunks[0]["metadata"]["dieu"])

    def test_embed_chunks(self):
        """Test embedding generation for chunks"""
        chunks = [
            {"content": "Điều 1. Nội dung A", "metadata": {"dieu": "1", "khoan": None}},
            {"content": "Điều 2. Nội dung B", "metadata": {"dieu": "2", "khoan": None}}
        ]
        
        embedded_objects = self.ocr_service.embed_chunks(chunks)
        
        self.assertEqual(len(embedded_objects), 2)
        # Check mapping
        self.assertEqual(embedded_objects[0]["content"], chunks[0]["content"])
        self.assertEqual(embedded_objects[0]["metadata"], chunks[0]["metadata"])
        # Check vector
        self.assertIn("vector", embedded_objects[0])
        self.assertIsInstance(embedded_objects[0]["vector"], list)
        self.assertGreater(len(embedded_objects[0]["vector"]), 0)
        # Check consistency (same dimension)
        self.assertEqual(len(embedded_objects[0]["vector"]), len(embedded_objects[1]["vector"]))

    @patch("httpx.AsyncClient.post")
    def test_rag_answer_groundedness_fail(self, mock_post):
        """Test groundedness fail when score is too low"""
        # 1. Setup mock data with very low scores
        chunk1 = {"content": "Nội dung không liên quan.", "final_score": 0.05}
        with patch.object(self.ocr_service, 'hybrid_search', return_value=[chunk1]):
            # 2. Call service
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(self.ocr_service.get_rag_answer("Câu hỏi bất kỳ"))
            
            # 3. Assertions
            self.assertEqual(result["answer"], "Dữ liệu tìm thấy không đủ tin cậy để trả lời.")
            self.assertFalse(result["grounded"])
            self.assertEqual(len(result["sources"]), 0)
            # Ensure LLM was NOT called
            mock_post.assert_not_called()

    @patch("httpx.AsyncClient.post")
    def test_rag_answer_hallucination_detected(self, mock_post):
        """Test post-validation for hallucination"""
        # 1. Setup mock data with high scores but hallucinated answer
        chunk1 = {"content": "Luật quy định về bảo hiểm.", "final_score": 0.8}
        
        # English text often tokenizes differently in PyVi. Let's use a long Vietnamese string
        # with absolutely NO overlap with chunk content.
        hallucinated_answer = "Trời hôm nay rất đẹp và tôi đang đi dạo ở công viên bách thảo."
        
        class MockResponse:
            def __init__(self):
                self.status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {"response": hallucinated_answer}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MockResponse()
            with patch.object(self.ocr_service, 'hybrid_search', return_value=[chunk1]):
                # 2. Call service
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(self.ocr_service.get_rag_answer("Bảo hiểm là gì?"))
                
                # Should hit the self-correction logic
                self.assertIn("không thể tìm thấy câu trả lời chính xác", result["answer"])
                self.assertFalse(result["grounded"])

    def test_supported_extensions(self):
        # We don't run full OCR test here because it requires system tools (Tesseract/Poppler)
        # But we can verify the check logic if we want, or just assume it works once configured.
        pass

if __name__ == "__main__":
    unittest.main()
