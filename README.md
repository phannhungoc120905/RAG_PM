# RAG_PM — Hệ thống AI tóm tắt và giao việc văn bản hành chính

## Tổng quan
Hệ thống này xử lý văn bản hành chính theo luồng: upload tài liệu, trích xuất text, làm sạch OCR, lưu metadata, sinh tóm tắt, hỏi đáp theo ngữ cảnh, tạo mind map và giao việc theo từng vai trò.

Các điểm đã được bổ sung gần đây:
- Hiển thị rõ tài liệu đang chọn ở các màn hình trợ lý AI của `agency_leader` và `staff`.
- Tăng độ bền cho OCR và RAG: fallback khi LLM lỗi, timeout đồng bộ theo `settings`, và chặn các câu trả lời rác/không đúng ngôn ngữ.
- Thêm endpoint và UI cho mind map từ văn bản đã chọn.
- Chuẩn hoá luồng giao việc ở cấp văn bản và cấp task chi tiết.

## Cài đặt

### 1. Cài thư viện
```bash
pip install -r requirements.txt
```

### 2. Cấu hình môi trường
```bash
cp .env.example .env
# Sửa .env với thông tin MySQL, đường dẫn Tesseract/Poppler và URL model LLM
```

### 3. Tạo database MySQL
```bash
mysql -u root -p -e "CREATE DATABASE ragpm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### 4. Chạy migration
```bash
alembic upgrade head
```

### 5. Khởi động server
```bash
python main.py
```

## Cấu trúc thư mục
```text
RAG_PM/
├── AI_STORAGE_CONTRACT.md
├── alembic.ini
├── config.py
├── main.py
├── README.md
├── requirements.txt
├── admin/
├── api/
├── auth/
├── db/
├── ocr/
├── templates/
└── uploads/
```

## Chức năng đã thay đổi

### 1. Trợ lý AI theo vai trò
- `admin`, `agency_leader`, `department_leader`, `staff` đều có khu vực trợ lý AI riêng.
- Hai màn hình `agency_leader` và `staff` đã có dropdown chọn tài liệu hiển thị rõ ràng trước khi hỏi đáp hoặc tạo mind map.
- Khi LLM trả về câu trả lời không đạt, hệ thống sẽ trả về đoạn trích từ chunk liên quan thay vì lỗi thô.

### 2. OCR và RAG
- Luồng OCR ưu tiên text layer của PDF, sau đó mới dùng OCR ảnh nếu cần.
- Có nhiều preset tiền xử lý ảnh, thử nhiều cấu hình Tesseract và chấm điểm kết quả theo tiếng Việt.
- Timeout gọi LLM được lấy từ `settings.OLLAMA_TIMEOUT_SECONDS` thay vì hardcode.
- Nếu Ollama không phản hồi hoặc trả kết quả kém, hệ thống fallback sang nội dung chunk đã trích xuất.

### 3. Mind map
- Thêm endpoint `POST /api/mindmap`.
- UI sẽ gọi LLM trước; nếu không ra Mermaid hợp lệ thì fallback sang node từ `ChunkMetadata`.
- Mind map hiện đang tối ưu cho tài liệu có cấu trúc rõ, như công văn, quyết định, báo cáo, tờ trình.

### 4. Giao việc
Luồng giao việc được chia thành 2 tầng:
- Cấp 1: hồ sơ giao việc theo văn bản.
- Cấp 2: task chi tiết cho phòng ban hoặc cá nhân.

Màn hình `agency_leader` dùng để tạo hồ sơ giao việc cấp văn bản và chia task xuống phòng ban/người xử lý. `department_leader` dùng để chia task cho staff trong phòng. `staff` chỉ xem task được giao và cập nhật tiến độ.

## Dữ liệu JSON cần chuẩn bị cho giao việc

### A. Tạo hồ sơ giao việc cấp văn bản
JSON gửi lên API thường có dạng:
```json
{
    "document_code": "CV-2026-001",
    "title": "Triển khai kế hoạch quý II",
    "content_summary": "Tóm tắt nội dung văn bản và các đầu việc chính.",
    "department_id": 4,
    "assigned_department_id": 7,
    "due_date": "2026-06-15",
    "status": "assigned"
}
```

Ý nghĩa các trường:
- `document_code`: mã hồ sơ giao việc.
- `title`: tiêu đề hồ sơ.
- `content_summary`: tóm tắt/diễn giải nội dung giao việc.
- `department_id`: phòng ban phát hành hoặc phòng chủ trì, nếu có.
- `assigned_department_id`: phòng nhận việc, nếu giao theo phòng.
- `due_date`: hạn hoàn thành theo định dạng `YYYY-MM-DD`.
- `status`: thường là `assigned` khi đã giao.

### B. Tạo task chi tiết
JSON tạo task con thường có dạng:
```json
{
    "work_document_id": 12,
    "title": "Soạn dự thảo công văn trả lời",
    "description": "Phối hợp với các phòng liên quan và gửi bản nháp trước 16h.",
    "assignee_user_id": 9,
    "department_id": 7,
    "position_id": 18,
    "priority": "high",
    "status": "pending",
    "due_date": "2026-06-10"
}
```

Ý nghĩa các trường:
- `work_document_id`: ID của hồ sơ giao việc cấp văn bản.
- `title`: tên task.
- `description`: mô tả chi tiết.
- `assignee_user_id`: người nhận task, có thể để `null` nếu giao theo phòng.
- `department_id`: phòng phụ trách task.
- `position_id`: vị trí công tác, nếu muốn lọc sâu hơn.
- `priority`: `normal`, `high` hoặc `urgent`.
- `status`: thường là `pending` hoặc `assigned` tuỳ luồng màn hình.
- `due_date`: hạn task theo định dạng `YYYY-MM-DD`.

### C. Dữ liệu cho mind map và tóm tắt
Các endpoint AI hiện dùng JSON tối giản:
```json
{
    "document_id": 12,
    "use_llm": true,
    "max_nodes": 12
}
```

Với tóm tắt/hỏi đáp, payload có thể gồm:
```json
{
    "document_id": 12,
    "query": "Tóm tắt các điểm cần lãnh đạo quyết định trong văn bản đã chọn",
    "top_k": 5,
    "document_ids": [12],
    "title": "Tóm tắt nhanh"
}
```

## Lưu ý về mind map và tóm tắt
- Hai chức năng này đã có fallback, nhưng chất lượng vẫn phụ thuộc mạnh vào chất lượng OCR và nội dung chunk đã lưu.
- Nếu văn bản scan kém, nhiều lỗi OCR, hoặc chunk quá ngắn, tóm tắt/mind map có thể chưa sát nghĩa.
- Khi LLM trả về câu quá ngắn, sai ngôn ngữ, hoặc không bám ngữ cảnh, hệ thống sẽ chuyển sang fallback; vì vậy kết quả có thể là trích đoạn thay vì câu trả lời diễn giải đầy đủ.
- Với tài liệu quan trọng, nên kiểm tra lại văn bản đã chọn trước khi tin hoàn toàn vào kết quả AI.

## API docs
`http://localhost:8000/docs`

## Dev A
Đọc `AI_STORAGE_CONTRACT.md` trước khi bắt đầu. Không tự gọi `os.getenv()`; dùng `from config import settings`.

## Dev B
Các endpoint nghiệp vụ sẽ nằm dưới `/api/...`. JWT bearer token lấy từ `/auth/login`, gửi qua header:

```text
Authorization: Bearer <access_token>
```
