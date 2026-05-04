# RAG_PM — Hệ thống AI tóm tắt văn bản hành chính

## Cài đặt

### 1. Clone và cài thư viện
```bash
pip install -r requirements.txt
```

### 2. Cấu hình môi trường
```bash
cp .env.example .env
# Sửa .env với thông tin MySQL và model path của bạn
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
├── .env.example
├── .gitignore
├── AI_STORAGE_CONTRACT.md
├── alembic.ini
├── config.py
├── history.json
├── index.html
├── logger.py
├── main.py
├── README.md
├── requirements.txt
├── admin/
│   ├── __init__.py
│   ├── router.py
│   └── service.py
├── api/
│   ├── __init__.py
│   └── router.py
├── auth/
│   ├── __init__.py
│   ├── dependencies.py
│   ├── middleware.py
│   ├── router.py
│   └── service.py
├── backups/
├── db/
│   ├── __init__.py
│   ├── database.py
│   ├── models.py
│   └── migrations/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
│           └── 0001_initial_schema.py
└── uploads/
    ├── done/
    ├── failed/
    └── processing/
```

## API docs
`http://localhost:8000/docs`

## Dev A
Đọc `AI_STORAGE_CONTRACT.md` trước khi bắt đầu. Không tự gọi `os.getenv()`; dùng `from config import settings`.

## Dev B
Các endpoint nghiệp vụ sẽ nằm dưới `/api/...`. JWT bearer token lấy từ `/auth/login`, gửi qua header:

```text
Authorization: Bearer <access_token>
```
