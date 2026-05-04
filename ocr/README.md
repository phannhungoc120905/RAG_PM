# OCR Module Overview

Module này cung cấp khả năng trích xuất văn bản từ hình ảnh và PDF hỗ trợ tiếng Việt.

## Cấu trúc
- `service.py`: Chứa logic xử lý OCR (Tesseract + pdf2image).
- `router.py`: API endpoint `/ocr/extract-text`.
- `requirements_ocr.txt`: Danh sách thư viện cần thiết.

## Yêu cầu hệ thống (System Requirements)
Để module hoạt động, bạn cần cài đặt các công cụ sau trên hệ điều hành:

1. **Tesseract OCR**:
   - Tải và cài đặt từ [Tesseract GitHub](https://github.com/UB-Mannheim/tesseract/wiki).
   - Trong quá trình cài đặt, chọn thêm gói ngôn ngữ **Vietnamese**.
   - Thêm đường dẫn thư mục cài đặt Tesseract vào biến môi trường `PATH`.

2. **Poppler**:
   - Cần thiết để `pdf2image` hoạt động (convert PDF sang ảnh).
   - Tải từ [Poppler cho Windows](http://blog.alivate.com.au/poppler-windows/).
   - Thêm thư mục `bin` của Poppler vào biến môi trường `PATH`.

## Sử dụng
Gửi request `POST` đến `/ocr/extract-text` với file đính kèm (multipart/form-data).
