# AI Storage Contract

## 1. Import config

```python
from config import settings

# AI settings
model_name = settings.MODEL_NAME
model_path = settings.MODEL_PATH
faiss_index_path = settings.FAISS_INDEX_PATH
vector_dim = settings.VECTOR_DIM
chunk_size = settings.CHUNK_SIZE
chunk_overlap = settings.CHUNK_OVERLAP
ocr_lang = settings.OCR_LANG
```

```python
# Khong tu goi os.getenv() o bat ky dau
```

## 2. Import logger

```python
from logger import get_logger

log = get_logger("ai.pipeline")
log.info("event_name", extra={"key": "value"})
```

## 3. DB Session trong background task

```python
from db.database import SessionLocal

db = SessionLocal()
try:
    # thao tac DB
    pass
finally:
    db.close()
```

## 4. Schema bang chunk_metadata

```python
{
    "document_id": int,      # lay tu bang documents sau khi file duoc upload
    "chunk_index": int,      # 0, 1, 2, ... theo thu tu chunk
    "page_number": int,      # trang bat dau cua chunk trong PDF
    "start_line": int,       # dong bat dau trong trang
    "faiss_index_id": int,   # index trong FAISS vector store
    "content_preview": str,  # 300 ky tu dau cua chunk
}
```

## 5. Schema bang summary_history

```python
{
    "document_id": int,
    "user_id": int,       # lay tu request context
    "summary_text": str,  # noi dung tom tat day du
    "is_reviewed": 0,
}
```

## 6. Quy uoc thu muc uploads

```text
uploads/processing/   <- Dev A doc file tu day
uploads/done/         <- Dev A move file vao day khi xong
uploads/failed/       <- Dev A move file vao day khi loi
```

```text
Dev C co cleanup job xoa file trong done/ sau 24h
```

## 7. Update trang thai document

```python
# Dev A phai update documents.status
"processing" -> "done"
"processing" -> "failed"
```

```python
# Neu failed, can ghi log day du
```

## 8. API endpoint Dev A can expose

```text
POST /api/upload
POST /api/summarize
GET  /api/search
GET  /api/history
```
