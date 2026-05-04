# OCR & RAG Legal System

Mô-đun này cung cấp khả năng trích xuất văn bản từ tài liệu (Hình ảnh, PDF), xử lý tiền dữ liệu, và tích hợp vào hệ thống RAG (Retrieval-Augmented Generation) chuyên dụng cho văn bản pháp luật.

## 🚀 Chức năng chính

### 1. Trích xuất văn bản (OCR)
- **Hỗ trợ định dạng:** PNG, JPG, JPEG, BMP và PDF.
- **Đa ngôn ngữ:** Tối ưu hóa cho tiếng Việt (`vie`) và tiếng Anh (`eng`).
- **Xử lý PDF:** Chuyển đổi PDF nhiều trang thành hình ảnh để trích xuất văn bản chất lượng cao.

### 2. Tiền xử lý dữ liệu (Preprocessing)
- **Chuẩn hóa Unicode:** Đảm bảo văn bản tiếng Việt nhất quán (NFC).
- **Lọc nhiễu:** Loại bỏ các ký tự rác từ quá trình OCR, định dạng lại khoảng trắng và ngắt dòng.
- **Smart Chunking:** Tự động nhận diện cấu trúc văn bản pháp luật (Điều, Khoản) để chia đoạn nhỏ mà không mất ngữ cảnh.

### 3. Tìm kiếm thông minh (Hybrid Search)
Kết hợp hai phương pháp tìm kiếm để đạt độ chính xác cao nhất:
- **BM25 (Keyword Search):** Tìm kiếm chính xác theo từ khóa pháp lý.
- **FAISS (Vector Search):** Tìm kiếm theo ý nghĩa ngữ nghĩa (Semantic mapping).
- **Ranking:** Tự động trộn và xếp hạng kết quả dựa trên trọng số tùy chỉnh.

### 4. RAG & Groundedness (Chống ảo giác)
- **Groundedness Check:** Kiểm tra độ liên quan của dữ liệu truy xuất trước khi trả lời.
- **Hallucination Prevention:** Đối soát câu trả lời của AI với ngữ cảnh gốc để đảm bảo tính xác thực pháp lý.
- **Dẫn nguồn:** Tự động trích dẫn các Điều/Khoản liên quan trong câu trả lời.

## 🛠 Cấu trúc thư mục
- `router.py`: API Endpoints (FastAPI).
- `service.py`: Logic cốt lõi (OCR, FAISS, BM25, RAG).
- `test_ocr.py`: Unit tests và Integration tests.

## 🚦 Yêu cầu hệ thống (System Requirements)
Để module hoạt động, bạn cần cài đặt các công cụ sau trên hệ điều hành:

1. **Tesseract OCR**:
   - Tải và cài đặt từ [Tesseract GitHub](https://github.com/UB-Mannheim/tesseract/wiki).
   - Trong quá trình cài đặt, chọn thêm gói ngôn ngữ **Vietnamese**.
   - Thêm đường dẫn thư mục cài đặt Tesseract vào biến môi trường `PATH`.

2. **Poppler**:
   - Cần thiết để `pdf2image` hoạt động (convert PDF sang ảnh).
   - Tải từ [Poppler cho Windows](https://github.com/oschwartz10612/poppler-windows/releases/).
   - Thêm thư mục `bin` của Poppler vào biến môi trường `PATH`.

## 📖 Hướng dẫn sử dụng
### Tải tài liệu lên hệ thống RAG
`POST /ocr/upload-process`
- Quy trình: OCR -> Normalize -> Chunking -> Embedding -> Store (FAISS).

### Tìm kiếm & Hỏi đáp
`POST /ocr/summarize`
- Sử dụng mô hình AI để trả lời câu hỏi dựa trên kho dữ liệu pháp luật đã tải lên.

