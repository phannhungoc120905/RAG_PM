import json
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from sqlalchemy import select
from fastapi import FastAPI, File, UploadFile
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from api.service import get_latest_history_public, upload_document
from ocr.router import router as ocr_router
from admin.router import router as admin_router
from api.router import router as api_router
from auth.middleware import add_middlewares
from auth.router import router as auth_router
from config import settings
from db.database import SessionLocal
from db.models import User
from logger import get_logger

log = get_logger("app.main")
HISTORY_FILE = "history.json"
TEMPLATES_DIR = Path("templates")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    for path in (
        Path(settings.UPLOAD_DIR) / "processing",
        Path(settings.UPLOAD_DIR) / "done",
        Path(settings.UPLOAD_DIR) / "failed",
        Path(settings.BACKUP_DIR),
    ):
        path.mkdir(parents=True, exist_ok=True)

    log.info("app_started", extra={"env": settings.DEBUG})
    yield


app = FastAPI(
    title="RAG_PM API",
    description="He thong AI tom tat van ban hanh chinh",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])
app.include_router(api_router, prefix="/api", tags=["AI"])
app.include_router(ocr_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
add_middlewares(app)


def get_history() -> list[dict]:
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []


def save_to_history(filename: str, summary: str) -> None:
    history = get_history()
    history.insert(
        0,
        {
            "filename": filename,
            "summary": summary,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    history = history[:20]
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)


def extract_text(file_path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text
    return text


def summarize_with_ollama(text: str) -> str:
    from langchain.chains import create_retrieval_chain
    from langchain.chains.combine_documents import create_stuff_documents_chain
    from langchain_community.vectorstores import FAISS
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_ollama import OllamaEmbeddings, OllamaLLM
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )
    chunks = text_splitter.create_documents([text])
    embeddings = OllamaEmbeddings(model=settings.MODEL_NAME)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    llm = OllamaLLM(model=settings.MODEL_NAME)
    prompt = ChatPromptTemplate.from_template(
        """
        Ban la mot tro ly tom tat van ban chuyen nghiep.
        Hay tom tat noi dung sau day thanh 5 y chinh quan trong nhat duoi dang danh sach bullet bang tieng Viet.
        Noi dung: {context}
        Tom tat:
        """
    )
    document_chain = create_stuff_documents_chain(llm, prompt)
    retriever = vectorstore.as_retriever()
    retrieval_chain = create_retrieval_chain(retriever, document_chain)
    response = retrieval_chain.invoke({"input": "Hay tom tat van ban nay"})
    return response["answer"]


def read_html_file(filename: str, fallback: str) -> str:
    path = TEMPLATES_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


def _serialize_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _slugify_filename(filename: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return sanitized or "document"


def _resolve_owner_id() -> int:
    db = SessionLocal()
    try:
        owner = db.scalar(select(User).where(User.is_active.is_(True)).order_by(User.id.asc()))
        if not owner:
            raise RuntimeError("Khong tim thay nguoi dung nao trong he thong de gan chu so huu tai lieu.")
        return owner.id
    finally:
        db.close()


def _persist_uploaded_file(file_bytes: bytes, original_filename: str) -> tuple[str, str]:
    upload_dir = Path(settings.UPLOAD_DIR) / "done"
    upload_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stored_name = f"{timestamp}_{_slugify_filename(original_filename)}"
    stored_path = upload_dir / stored_name
    stored_path.write_bytes(file_bytes)
    return stored_name, str(stored_path)


def _save_document_result(
    *,
    file_bytes: bytes,
    original_filename: str,
    result: dict,
    summary: str,
    mime_type: str | None = None,
) -> None:
    owner_id = _resolve_owner_id()
    stored_name, stored_path = _persist_uploaded_file(file_bytes, original_filename)
    db = SessionLocal()
    try:
        document = Document(
            filename=stored_name,
            original_filename=original_filename,
            file_path=stored_path,
            file_size_kb=max(1, len(file_bytes) // 1024) if file_bytes else 0,
            status="processed",
            document_type=result["classification"].get("document_type"),
            document_number=result["structure"].get("document_code"),
            document_title=result["structure"].get("summary"),
            document_summary=summary,
            source_format=result.get("extension"),
            mime_type=mime_type,
            page_count=result.get("page_count"),
            ocr_text=result.get("raw_text"),
            clean_text=result.get("clean_text"),
            processing_status="completed",
            classification_label=result["classification"].get("document_type"),
            classification_score=result["classification"].get("confidence"),
            structure_json=_serialize_json(result.get("structure")),
            page_index_json=_serialize_json(result.get("page_index")),
            storage_meta_json=_serialize_json({"supported_formats": result.get("supported_formats", [])}),
            owner_id=owner_id,
            uploaded_by=owner_id,
            processed_by=owner_id,
            review_status="pending",
            created_at=datetime.now(),
            processed_at=datetime.now(),
        )
        db.add(document)
        db.flush()

        embedded_chunks = legacy_ocr_service.embed_chunks(result.get("chunks", []))
        legacy_ocr_service.store_embeddings(embedded_chunks)

        for index, chunk in enumerate(result.get("chunks", [])):
            metadata = chunk.get("metadata", {})
            vector_metadata = embedded_chunks[index]["metadata"] if index < len(embedded_chunks) else metadata
            db.add(
                ChunkMetadata(
                    document_id=document.id,
                    chunk_index=index,
                    chunk_type="semantic",
                    section_type="article_clause" if metadata.get("dieu") else "free_text",
                    section_code=(
                        f"Dieu {metadata.get('dieu')}/Khoan {metadata.get('khoan')}"
                        if metadata.get("dieu") and metadata.get("khoan")
                        else (f"Dieu {metadata.get('dieu')}" if metadata.get("dieu") else None)
                    ),
                    section_title=(chunk.get("content", "")[:500] or None),
                    page_number=metadata.get("page_number"),
                    start_line=metadata.get("start_line"),
                    end_line=metadata.get("end_line"),
                    end_page=metadata.get("page_number"),
                    token_count=len(chunk.get("content", "").split()),
                    embedding_status="completed" if index < len(embedded_chunks) else "pending",
                    embedding_model="fallback-local",
                    bm25_text=chunk.get("content"),
                    citation_json=_serialize_json(
                        {
                            "page_number": metadata.get("page_number"),
                            "page_label": metadata.get("page_label"),
                            "dieu": metadata.get("dieu"),
                            "khoan": metadata.get("khoan"),
                        }
                    ),
                    metadata_json=_serialize_json(vector_metadata),
                    content_preview=chunk.get("content", "")[:400] or None,
                )
            )

        db.add(
            SummaryHistory(
                document_id=document.id,
                user_id=owner_id,
                summary_type="summary",
                version_no=1,
                title=result["structure"].get("summary") or original_filename,
                summary_text=summary,
                prompt_template="default_admin_summary",
                model_name=settings.MODEL_NAME,
                source_chunk_ids_json=_serialize_json(list(range(len(result.get("chunks", []))))),
                groundedness_score=None,
                hallucination_flag=False,
                is_reviewed=False,
            )
        )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@app.get("/login", response_class=HTMLResponse)
async def login_page() -> str:
    return read_html_file("admin_login_new.html", "<h1>RAG_PM Login</h1>")


@app.get("/", response_class=HTMLResponse)
async def summarizer_home_page() -> str:
    return read_html_file("index_main.html", "<h1>AI PDF Summarizer</h1>")


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard_page() -> str:
    return read_html_file("admin_dashboard_new.html", "<h1>RAG_PM Admin Dashboard</h1>")


@app.get("/summarizer", response_class=HTMLResponse)
async def summarizer_page() -> str:
    return read_html_file("index.html", "<h1>AI PDF Summarizer</h1>")


@app.get("/history")
async def history() -> list[dict]:
    db = SessionLocal()
    try:
        return get_latest_history_public(db)
    finally:
        db.close()


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    db = SessionLocal()
    try:
        contents = await file.read()
        owner_id = _resolve_owner_id()
        owner = db.get(User, owner_id)
        if not owner:
            return {"error": "Khong tim thay nguoi dung de xu ly tai lieu."}
        document, summary = await upload_document(
            db,
            current_user=owner,
            file_bytes=contents,
            original_filename=file.filename,
            mime_type=file.content_type,
            auto_summary=True,
        )
        page_index = json.loads(document.page_index_json) if document.page_index_json else []
        structure = json.loads(document.structure_json) if document.structure_json else {}
        classification = {
            "document_type": document.classification_label,
            "confidence": float(document.classification_score) if document.classification_score is not None else None,
        }
        return {
            "summary": summary.summary_text if summary else None,
            "page_count": document.page_count,
            "page_index": page_index,
            "classification": classification,
            "structure": structure,
            "document_id": document.id,
        }
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=False)
        log.error("legacy_upload_http_error", extra={"uploaded_file": file.filename, "detail": detail})
        return {"error": detail}
    except Exception as exc:
        detail = str(exc) or repr(exc)
        log.error("legacy_upload_failed", extra={"uploaded_file": file.filename, "error": detail})
        return {"error": detail}
    finally:
        db.close()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
