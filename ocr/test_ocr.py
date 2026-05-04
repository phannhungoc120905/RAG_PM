import asyncio
import io
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ocr.service import OCRService


class TestOCR(unittest.TestCase):
    def setUp(self):
        base_dir = Path(__file__).resolve().parent / ".tmp_testdata"
        base_dir.mkdir(exist_ok=True)
        self.temp_dir = tempfile.mkdtemp(prefix="ocr_test_", dir=base_dir)
        self.test_index = os.path.join(self.temp_dir, "test_ocr.index")
        self.test_metadata = os.path.join(self.temp_dir, "test_metadata.json")
        self.ocr_service = OCRService(index_path=self.test_index, metadata_path=self.test_metadata)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_process_txt_document(self):
        raw = (
            "UBND THANH PHO HANOI\n"
            "Trang 1\n"
            "CONG VAN\n"
            "So: 12/CV-UBND\n"
            "Ve viec huong dan nghiep vu.\f"
            "UBND THANH PHO HANOI\n"
            "Trang 2\n"
            "Dieu 1. Noi dung xu ly.\n"
            "1. Nhiem vu thu nhat."
        ).encode("utf-8")

        result = self.ocr_service.process_document(raw, "sample.txt")

        self.assertEqual(result["extension"], "txt")
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(result["classification"]["document_type"], "cong_van")
        self.assertEqual(result["structure"]["document_code"], "12/CV-UBND")
        self.assertGreaterEqual(len(result["chunks"]), 1)
        self.assertTrue(all("Trang 1" not in page["text"] for page in result["pages"]))

    def test_process_docx_document(self):
        docx_bytes = self._build_minimal_docx(
            [
                ["THONG BAO", "So: 99/TB", "Ve viec cap nhat lich hop."],
                ["Dieu 1. Lich hop moi", "Khoan 1. Thoi gian bat dau."],
            ]
        )

        result = self.ocr_service.process_document(docx_bytes, "notice.docx")

        self.assertEqual(result["extension"], "docx")
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(result["classification"]["document_type"], "thong_bao")
        self.assertEqual(result["structure"]["article_count"], 1)
        self.assertEqual(result["page_index"][0]["page_number"], 1)

    def test_clean_pages_removes_repeated_headers_and_footers(self):
        pages = [
            {"page_number": 1, "text": "HEADER\nTrang 1\nNoi dung trang mot\nFOOTER"},
            {"page_number": 2, "text": "HEADER\nTrang 2\nNoi dung trang hai\nFOOTER"},
        ]

        cleaned = self.ocr_service.clean_pages(pages)

        self.assertEqual(cleaned[0]["text"], "Noi dung trang mot")
        self.assertEqual(cleaned[1]["text"], "Noi dung trang hai")

    def test_chunk_text_has_page_metadata(self):
        chunks = self.ocr_service.chunk_text(
            "Dieu 1. Quy dinh chung\n1. Khoan mot\n2. Khoan hai",
            page_number=3,
            page_label="(Trang 3)",
        )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["metadata"]["page_number"], 3)
        self.assertEqual(chunks[0]["metadata"]["dieu"], "1")
        self.assertEqual(chunks[1]["metadata"]["khoan"], "2")

    def test_embed_chunks_uses_fallback_shape(self):
        chunks = [
            {"content": "Dieu 1. Noi dung A", "metadata": {"dieu": "1"}},
            {"content": "Dieu 2. Noi dung B", "metadata": {"dieu": "2"}},
        ]

        embedded = self.ocr_service.embed_chunks(chunks)

        self.assertEqual(len(embedded), 2)
        self.assertEqual(len(embedded[0]["vector"]), 384)

    def test_hybrid_search_preserves_page_metadata(self):
        chunks = [
            {
                "content": "Dieu 1. Cong van ve tai chinh",
                "metadata": {"page_number": 1, "page_label": "(Trang 1)", "dieu": "1"},
            },
            {
                "content": "Dieu 2. Quy dinh nhan su",
                "metadata": {"page_number": 2, "page_label": "(Trang 2)", "dieu": "2"},
            },
        ]

        embedded = self.ocr_service.embed_chunks(chunks)
        self.ocr_service.store_embeddings(embedded)
        results = self.ocr_service.hybrid_search("tai chinh", top_k=5, threshold=0.0)

        self.assertGreater(len(results), 0)
        self.assertIn("metadata", results[0])
        self.assertIn("page_number", results[0]["metadata"])

    def test_rag_answer_mock(self):
        chunks = [
            {
                "content": "Dieu 1. Quy dinh ve lao dong.",
                "metadata": {"dieu": "1", "page_number": 1, "page_label": "(Trang 1)"},
            }
        ]
        embedded = self.ocr_service.embed_chunks(chunks)
        self.ocr_service.store_embeddings(embedded)

        class MockResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"response": "Theo Dieu 1, day la quy dinh ve lao dong."}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MockResponse()
            result = asyncio.run(self.ocr_service.get_rag_answer("lao dong la gi"))

        self.assertEqual(result["answer"], "Theo Dieu 1, day la quy dinh ve lao dong.")
        self.assertEqual(result["source_chunks"][0]["metadata"]["page_number"], 1)

    def test_rag_no_info(self):
        result = asyncio.run(self.ocr_service.get_rag_answer("thong tin khong ton tai"))
        self.assertEqual(result["answer"], "Khong tim thay thong tin phu hop trong tai lieu.")
        self.assertEqual(result["sources"], [])

    def test_detect_document_structure(self):
        text = "QUYET DINH\nSo: 15/QD-UBND\nDieu 1. Ban hanh quy che.\nKhoan 1. Noi dung."
        structure = self.ocr_service.detect_document_structure(text)

        self.assertEqual(structure["document_code"], "15/QD-UBND")
        self.assertEqual(structure["article_count"], 1)
        self.assertEqual(structure["clause_count"], 1)

    def _build_minimal_docx(self, pages: list[list[str]]) -> bytes:
        body_parts = []
        for page_index, lines in enumerate(pages):
            for line in lines:
                body_parts.append(
                    f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>"
                )
            if page_index < len(pages) - 1:
                body_parts.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

        document_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{''.join(body_parts)}</w:body>"
            "</w:document>"
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        )
        rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>"
        )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("_rels/.rels", rels)
            archive.writestr("word/document.xml", document_xml)
        return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
