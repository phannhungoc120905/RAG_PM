from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest import result

import httpx
from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from config import settings
from db.models import ChunkMetadata, Document, SummaryHistory, SystemLog, User
from logger import get_logger
from ocr.runtime import ocr_service


log = get_logger("api.service")


def get_supported_formats() -> list[str]:
    return ["pdf", "docx", "txt", "jpg", "jpeg", "png", "bmp", "tif", "tiff"]


async def check_ollama_health() -> dict[str, Any]:

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(settings.OLLAMA_TAGS_URL, timeout=10.0)
            response.raise_for_status()
            payload = response.json()
        models = [item.get("name") for item in payload.get("models", []) if item.get("name")]
        return {
            "ok": True,
            "base_url": settings.OLLAMA_BASE_URL,
            "model_name": settings.MODEL_NAME,
            "available_models": models,
        }
    except Exception as exc:
        return {
            "ok": False,
            "base_url": settings.OLLAMA_BASE_URL,
            "model_name": settings.MODEL_NAME,
            "error": str(exc),
        }


def list_documents(
    db: Session,
    *,
    current_user: User,
    page: int,
    page_size: int,
    search: str | None = None,
    document_type: str | None = None,
    processing_status: str | None = None,
    review_status: str | None = None,
) -> tuple[list[Document], int]:
    statement: Select[tuple[Document]] = select(Document).options(
        selectinload(Document.owner),
        selectinload(Document.summaries),
    ).where(Document.deleted_at.is_(None))
    count_statement = select(func.count()).select_from(Document).where(Document.deleted_at.is_(None))

    if current_user.role != "admin":
        statement = statement.where(Document.owner_id == current_user.id)
        count_statement = count_statement.where(Document.owner_id == current_user.id)

    if search:
        criteria = or_(
            Document.original_filename.ilike(f"%{search}%"),
            Document.document_title.ilike(f"%{search}%"),
            Document.document_number.ilike(f"%{search}%"),
            Document.document_type.ilike(f"%{search}%"),
            Document.classification_label.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)

    if document_type:
        statement = statement.where(Document.document_type == document_type)
        count_statement = count_statement.where(Document.document_type == document_type)
    if processing_status:
        statement = statement.where(Document.processing_status == processing_status)
        count_statement = count_statement.where(Document.processing_status == processing_status)
    if review_status:
        statement = statement.where(Document.review_status == review_status)
        count_statement = count_statement.where(Document.review_status == review_status)

    total = db.scalar(count_statement) or 0
    items = db.scalars(
        statement.order_by(Document.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return items, total


def get_document_detail(db: Session, document_id: int, current_user: User) -> Document:
    document = db.scalar(
        select(Document)
        .options(
            selectinload(Document.owner),
            selectinload(Document.chunks),
            selectinload(Document.summaries),
        )
        .where(Document.id == document_id, Document.deleted_at.is_(None))
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    _assert_document_access(document, current_user)
    return document


async def upload_document(
    db: Session,
    *,
    current_user: User,
    file_bytes: bytes,
    original_filename: str,
    mime_type: str | None = None,
    auto_summary: bool = False,
) -> tuple[Document, SummaryHistory | None]:
    final_path: Path | None = None     
    embeddings_written = False        
    if not original_filename or "." not in original_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")    
    extension = original_filename.rsplit(".", 1)[-1].lower()
    if extension not in get_supported_formats():
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {extension}")

    processing_path = _write_upload_file(file_bytes, original_filename, "processing")
    document = Document(
        filename=processing_path.name,
        original_filename=original_filename,
        file_path=str(processing_path),
        file_size_kb=max(1, len(file_bytes) // 1024) if file_bytes else 0,
        status="processing",
        source_format=extension,
        mime_type=mime_type,
        owner_id=current_user.id,
        uploaded_by=current_user.id,
        processing_status="processing",
        review_status="pending",
        created_at=datetime.now(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        result = ocr_service.process_document(file_bytes, original_filename)
        print("DEBUG chunks type:", type(result.get("chunks", [])))
        print("DEBUG chunks sample:", str(result.get("chunks", []))[:300])

        final_path = _move_upload_file(processing_path, "done")
        enriched_chunks = _build_enriched_chunks(document.id, result.get("chunks", []))
        start_vector_id = int(ocr_service.index.ntotal)
        embedded_chunks = ocr_service.embed_chunks(enriched_chunks)
        ocr_service.store_embeddings(embedded_chunks)
        embeddings_written = True

        for index, chunk in enumerate(enriched_chunks):
            metadata = chunk.get("metadata", {})
            db.add(
                ChunkMetadata(
                    document_id=document.id,
                    chunk_index=index,
                    chunk_type=metadata.get("section_type") or "semantic",
                    section_type=metadata.get("section_type"),
                    section_code=_section_code(metadata),
                    section_title=metadata.get("anchor_text"),
                    page_number=metadata.get("page_number"),
                    start_line=metadata.get("start_line"),
                    end_line=metadata.get("end_line"),
                    end_page=metadata.get("page_number"),
                    token_count=len(chunk.get("content", "").split()),
                    faiss_index_id=start_vector_id + index,
                    embedding_status="completed",
                    embedding_model=settings.EMBEDDING_MODEL_NAME,
                    bm25_text=chunk.get("content"),
                    citation_json=_json_dumps(
                        {
                            "page_number": metadata.get("page_number"),
                            "page_label": metadata.get("page_label"),
                            "start_line": metadata.get("start_line"),
                            "end_line": metadata.get("end_line"),
                            "dieu": metadata.get("dieu"),
                            "khoan": metadata.get("khoan"),
                        }
                    ),
                    metadata_json=_json_dumps(metadata),
                    content_preview=chunk.get("content", "")[:400] or None,
                )
            )

        document.filename = final_path.name
        document.file_path = str(final_path)
        document.status = "processed"
        document.document_type = result["classification"].get("document_type")
        document.document_number = result["structure"].get("document_code")
        document.document_title = result["structure"].get("summary") or original_filename
        document.page_count = result.get("page_count")
        document.ocr_text = result.get("raw_text")
        document.clean_text = result.get("clean_text")
        document.processing_status = "completed"
        document.processing_error = None
        document.classification_label = result["classification"].get("document_type")
        document.classification_score = result["classification"].get("confidence")
        document.structure_json = _json_dumps(result.get("structure"))
        document.page_index_json = _json_dumps(result.get("page_index"))
        document.storage_meta_json = _json_dumps({"supported_formats": result.get("supported_formats", get_supported_formats())})
        document.processed_by = current_user.id
        document.processed_at = datetime.now()
        document.updated_at = datetime.now()
        db.add(document)
        db.commit()
        db.refresh(document)

        _write_system_log(
            db,
            user_id=current_user.id,
            action="document_upload",
            detail=_json_dumps({"document_id": document.id, "filename": original_filename}),
            module_name="api.documents",
            entity_type="document",
            entity_id=document.id,
            log_type="usage",
        )
    except Exception as e:
        db.rollback()
        if embeddings_written:
            try:
                _rebuild_vector_storage(db)
            except Exception:
                log.exception("upload_vector_rebuild_failed", document_id=document.id)
        if final_path and final_path.exists():
            try:
                failed_path = _move_upload_file(final_path, "failed")
                document.file_path = str(failed_path)
                document.filename = failed_path.name
            except Exception:
                log.exception("upload_failed_file_move_failed", document_id=document.id, filename=original_filename)
        log.error("upload_processing_failed", extra={"document_id": document.id, "error": str(e)})
        document.processing_status = "failed"
        document.status = "failed"
        document.processing_error = str(e)
        document.updated_at = datetime.now()
        db.add(document)
        db.commit()
        log.exception(
            "document_upload_failed",
            document_id=document.id,
            filename=original_filename,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý tài liệu: {str(e)}")
    summary_record = None
    if auto_summary:
        try:
            summary_record = await create_summary_for_document(
                db,
                document_id=document.id,
                current_user=current_user,
            )
        except Exception:
            log.exception(
                "document_auto_summary_failed",
                document_id=document.id,
                filename=original_filename,
            )

    return document, summary_record


async def create_summary_for_document(
    db: Session,
    *,
    document_id: int,
    current_user: User,
    title: str | None = None,
    prompt_template: str = "default_admin_summary",
) -> SummaryHistory:
    document = get_document_detail(db, document_id, current_user)
    if not document.clean_text:
        raise HTTPException(status_code=400, detail="Document has no extracted text to summarize")

    chunk_ids = [chunk.id for chunk in sorted(document.chunks, key=lambda item: item.chunk_index or 0)]
    prompt = _build_summary_prompt(document)
    summary_text = await _generate_llm_text(prompt)
    if not summary_text:
        raise HTTPException(status_code=502, detail="Model did not return a summary")

    version_no = (db.scalar(select(func.max(SummaryHistory.version_no)).where(SummaryHistory.document_id == document.id)) or 0) + 1
    summary = SummaryHistory(
        document_id=document.id,
        user_id=current_user.id,
        summary_type="summary",
        version_no=version_no,
        title=title or document.document_title or document.original_filename,
        summary_text=summary_text,
        prompt_template=prompt_template,
        model_name=settings.MODEL_NAME,
        source_chunk_ids_json=_json_dumps(chunk_ids),
        groundedness_score=1.0 if chunk_ids else 0.0,
        hallucination_flag=False,
        is_reviewed=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    document.document_summary = summary_text
    document.updated_at = datetime.now()
    db.add(summary)
    db.add(document)
    db.commit()
    db.refresh(summary)

    _write_system_log(
        db,
        user_id=current_user.id,
        action="document_summarize",
        detail=_json_dumps({"document_id": document.id, "summary_id": summary.id, "version_no": version_no}),
        module_name="api.summaries",
        entity_type="summary",
        entity_id=summary.id,
        log_type="usage",
    )
    return summary


async def answer_question(
    db: Session,
    *,
    current_user: User,
    query: str,
    top_k: int = 5,
    document_ids: list[int] | None = None,
) -> dict[str, Any]:
    allowed_document_ids = _resolve_allowed_document_ids(db, current_user, document_ids)
    return await ocr_service.get_rag_answer(query, top_k=top_k, document_ids=allowed_document_ids)


def search_chunks(
    db: Session,
    *,
    current_user: User,
    query: str,
    top_k: int = 5,
    document_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    allowed_document_ids = _resolve_allowed_document_ids(db, current_user, document_ids)
    return ocr_service.hybrid_search(query, top_k=top_k, threshold=0.0, document_ids=allowed_document_ids)


def list_history(
    db: Session,
    *,
    current_user: User | None,
    page: int,
    page_size: int,
    document_id: int | None = None,
) -> tuple[list[SummaryHistory], int]:
    statement: Select[tuple[SummaryHistory]] = select(SummaryHistory).options(
        selectinload(SummaryHistory.document),
        selectinload(SummaryHistory.user),
    ).where(SummaryHistory.is_deleted.is_(False))
    count_statement = select(func.count()).select_from(SummaryHistory).where(SummaryHistory.is_deleted.is_(False))

    if current_user and current_user.role != "admin":
        statement = statement.join(Document, SummaryHistory.document_id == Document.id).where(Document.owner_id == current_user.id)
        count_statement = count_statement.join(Document, SummaryHistory.document_id == Document.id).where(Document.owner_id == current_user.id)
    if document_id is not None:
        statement = statement.where(SummaryHistory.document_id == document_id)
        count_statement = count_statement.where(SummaryHistory.document_id == document_id)

    total = db.scalar(count_statement) or 0
    items = db.scalars(
        statement.order_by(SummaryHistory.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return items, total


def get_summary_detail(db: Session, summary_id: int, current_user: User) -> SummaryHistory:
    summary = db.scalar(
        select(SummaryHistory)
        .options(
            selectinload(SummaryHistory.document).selectinload(Document.chunks),
            selectinload(SummaryHistory.user),
        )
        .where(SummaryHistory.id == summary_id, SummaryHistory.is_deleted.is_(False))
    )
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    _assert_document_access(summary.document, current_user)
    return summary


def review_summary(
    db: Session,
    *,
    summary_id: int,
    current_user: User,
    approved: bool,
    note: str | None,
) -> SummaryHistory:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required for review")

    summary = get_summary_detail(db, summary_id, current_user)
    summary.is_reviewed = approved
    summary.reviewed_by = current_user.id
    summary.review_note = note
    summary.updated_at = datetime.now()
    summary.document.review_status = "approved" if approved else "needs_revision"
    summary.document.reviewed_by = current_user.id
    summary.document.reviewed_at = datetime.now()
    summary.document.updated_at = datetime.now()
    db.add(summary)
    db.add(summary.document)
    db.commit()
    db.refresh(summary)
    return summary


def leave_summary_feedback(
    db: Session,
    *,
    summary_id: int,
    current_user: User,
    score: int | None,
    comment: str | None,
) -> SummaryHistory:
    summary = get_summary_detail(db, summary_id, current_user)
    summary.feedback_score = score
    summary.feedback_comment = comment
    summary.updated_at = datetime.now()
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


def export_summary(db: Session, *, summary_id: int, current_user: User, export_format: str) -> Path:
    summary = get_summary_detail(db, summary_id, current_user)
    export_format = export_format.lower()
    export_dir = Path(settings.BACKUP_DIR) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    safe_title = _slugify_filename(summary.title or f"summary_{summary.id}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if export_format == "txt":
        export_path = export_dir / f"{safe_title}_{timestamp}.txt"
        export_path.write_text(summary.summary_text or "", encoding="utf-8")
    elif export_format == "json":
        export_path = export_dir / f"{safe_title}_{timestamp}.json"
        export_path.write_text(
            _json_dumps(
                {
                    "summary_id": summary.id,
                    "document_id": summary.document_id,
                    "title": summary.title,
                    "summary_text": summary.summary_text,
                    "model_name": summary.model_name,
                    "created_at": summary.created_at,
                }
            ),
            encoding="utf-8",
        )
    elif export_format == "docx":
        try:
            # pyrefly: ignore [missing-import]
            from docx import Document as WordDocument
        except ImportError as exc:
            raise HTTPException(status_code=501, detail="python-docx is required for DOCX export") from exc
        export_path = export_dir / f"{safe_title}_{timestamp}.docx"
        word_doc = WordDocument()
        word_doc.add_heading(summary.title or "Summary", level=1)
        word_doc.add_paragraph(summary.summary_text or "")
        word_doc.save(export_path)
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format")

    exported_formats = _json_loads(summary.exported_formats_json, default=[])
    exported_formats.append({"format": export_format, "path": str(export_path), "exported_at": datetime.now().isoformat()})
    summary.exported_formats_json = _json_dumps(exported_formats)
    summary.updated_at = datetime.now()
    db.add(summary)
    db.commit()
    return export_path


def delete_document_cascade(db: Session, *, document_id: int, current_user: User) -> dict[str, Any]:
    document = get_document_detail(db, document_id, current_user)
    file_path = Path(document.file_path) if document.file_path else None
    payload = {"document_id": document.id, "filename": document.original_filename}
    document.deleted_at = datetime.now()
    document.updated_at = datetime.now()
    document.processing_status = "deleted"
    document.status = "deleted"
    db.add(document)
    db.commit()

    if file_path and file_path.exists():
        file_path.unlink(missing_ok=True)

    _rebuild_vector_storage(db)
    _write_system_log(
        db,
        user_id=current_user.id,
        action="document_delete",
        detail=_json_dumps(payload),
        module_name="api.documents",
        entity_type="document",
        entity_id=document_id,
        log_type="usage",
    )
    return payload


def get_latest_history_public(db: Session, limit: int = 20) -> list[dict[str, Any]]:
    items = db.scalars(
        select(SummaryHistory)
        .options(selectinload(SummaryHistory.document))
        .where(SummaryHistory.is_deleted.is_(False))
        .order_by(SummaryHistory.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": item.id,
            "document_id": item.document_id,
            "filename": item.document.original_filename if item.document else None,
            "title": item.title,
            "summary": item.summary_text,
            "timestamp": item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else None,
        }
        for item in items
    ]


def _resolve_allowed_document_ids(db: Session, current_user: User, document_ids: list[int] | None) -> list[int] | None:
    if current_user.role == "admin":
        return document_ids

    requested_ids = set(document_ids or [])
    owned_ids = set(
        db.scalars(select(Document.id).where(Document.owner_id == current_user.id, Document.deleted_at.is_(None))).all()
    )
    if requested_ids:
        forbidden = requested_ids - owned_ids
        if forbidden:
            raise HTTPException(status_code=403, detail="You do not have access to one or more requested documents")
        return list(requested_ids)
    return list(owned_ids)


def _assert_document_access(document: Document, current_user: User) -> None:
    if current_user.role == "admin":
        return
    if document.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this document")


def _build_enriched_chunks(document_id: int, chunks: list) -> list[dict[str, Any]]:
    enriched_chunks: list[dict[str, Any]] = []
    for index, raw_chunk in enumerate(chunks):  # ← đổi tên biến thành raw_chunk
        if isinstance(raw_chunk, str):
            chunk = {"content": raw_chunk, "metadata": {}}
        elif isinstance(raw_chunk, dict):
            chunk = raw_chunk
        else:
            chunk = {"content": str(raw_chunk), "metadata": {}}

        metadata = dict(chunk.get("metadata", {}))
        metadata["document_id"] = document_id
        metadata["chunk_index"] = index
        metadata["citation_anchor"] = _build_citation_anchor(metadata)
        enriched_chunks.append({"content": chunk.get("content", ""), "metadata": metadata})
    return enriched_chunks

def _build_citation_anchor(metadata: dict[str, Any]) -> str:
    page = metadata.get("page_number")
    start_line = metadata.get("start_line")
    end_line = metadata.get("end_line")
    if page and start_line and end_line:
        return f"Trang {page}, dong {start_line}-{end_line}"
    if page:
        return f"Trang {page}"
    return ""


def _section_code(metadata: dict[str, Any]) -> str | None:
    dieu = metadata.get("dieu")
    khoan = metadata.get("khoan")
    if dieu and khoan:
        return f"Dieu {dieu}/Khoan {khoan}"
    if dieu:
        return f"Dieu {dieu}"
    return None


def _write_upload_file(file_bytes: bytes, original_filename: str, stage: str) -> Path:
    target_dir = Path(settings.UPLOAD_DIR) / stage
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stored_name = f"{timestamp}_{_slugify_filename(original_filename)}"
    stored_path = target_dir / stored_name
    stored_path.write_bytes(file_bytes)
    return stored_path


def _move_upload_file(path: Path, stage: str) -> Path:
    if not path.exists():
        return path
    target_dir = Path(settings.UPLOAD_DIR) / stage
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / path.name

    # Windows deployments in this workspace can create files that are readable
    # but not deletable from the processing folder. Prefer copy + best-effort
    # cleanup so upload/summarize does not fail on stage transitions.
    if target_path.exists():
        target_path.unlink(missing_ok=True)
    shutil.copy2(path, target_path)
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        log.warning(
            "upload_stage_cleanup_skipped",
            extra={"source_path": str(path), "target_path": str(target_path), "stage": stage},
        )
    return target_path


def _slugify_filename(filename: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return sanitized or "document"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _write_system_log(
    db: Session,
    *,
    action: str,
    user_id: int | None = None,
    detail: str | None = None,
    module_name: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    log_type: str = "system",
) -> None:
    db.add(
        SystemLog(
            user_id=user_id,
            action=action,
            detail=detail,
            status_code=200,
            module_name=module_name,
            entity_type=entity_type,
            entity_id=entity_id,
            log_type=log_type,
            created_at=datetime.now(),
        )
    )
    db.commit()


async def _generate_llm_text(prompt: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.OLLAMA_GENERATE_URL,
            json={
                "model": settings.MODEL_NAME,
                "prompt": prompt,
                "stream": False,
            },
            timeout=httpx.Timeout(settings.OLLAMA_TIMEOUT_SECONDS, connect=10.0),
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()


def _build_summary_prompt(document: Document) -> str:
    document_number = document.document_number or "Khong ro so hieu"
    document_type = document.document_type or "van_ban"
    title = document.document_title or document.original_filename or "tai lieu"
    return (
        "Ban la tro ly tong hop van ban hanh chinh cho khoi nha nuoc.\n"
        "Hay tao ban tom tat bang tieng Viet ro rang, ngan gon, co cau truc.\n"
        "Tra ve 5 muc: 1) Thong tin chung 2) Muc tieu 3) Noi dung chinh 4) Don vi/thoi han 5) Luu y.\n"
        "Khong tu bo sung thong tin khong co trong tai lieu.\n\n"
        f"So hieu: {document_number}\n"
        f"Loai van ban: {document_type}\n"
        f"Tieu de: {title}\n\n"
        f"NOI DUNG:\n{document.clean_text or ''}\n\n"
        "BAN TOM TAT:"
    )


def _rebuild_vector_storage(db: Session) -> None:
    rows = db.scalars(
        select(ChunkMetadata)
        .join(Document, ChunkMetadata.document_id == Document.id)
        .where(Document.deleted_at.is_(None))
        .order_by(ChunkMetadata.document_id.asc(), ChunkMetadata.chunk_index.asc())
    ).all()

    if not rows:
        ocr_service.reset_storage()
        return

    chunks = []
    for row in rows:
        metadata = _json_loads(row.metadata_json, default={})
        metadata.setdefault("document_id", row.document_id)
        metadata.setdefault("chunk_index", row.chunk_index)
        metadata.setdefault("page_number", row.page_number)
        metadata.setdefault("start_line", row.start_line)
        metadata.setdefault("end_line", row.end_line)
        metadata.setdefault("section_type", row.section_type)
        chunks.append({"content": row.bm25_text or row.content_preview or "", "metadata": metadata})

    ocr_service.reset_storage()
    ocr_service.store_embeddings(ocr_service.embed_chunks(chunks))
