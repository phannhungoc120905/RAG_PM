from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.service import (
    answer_question,
    check_ollama_health,
    create_summary_for_document,
    delete_document_cascade,
    export_summary,
    get_document_detail,
    get_supported_formats,
    get_summary_detail,
    leave_summary_feedback,
    list_documents,
    list_history,
    review_summary,
    search_chunks,
    upload_document,
)
from auth.dependencies import require_active_user
from db.database import get_db
from db.models import Document, SummaryHistory, User


router = APIRouter()


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    document_ids: list[int] | None = None


class SummarizeRequest(BaseModel):
    document_id: int | None = None
    query: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    document_ids: list[int] | None = None
    title: str | None = None


class ReviewRequest(BaseModel):
    approved: bool
    note: str | None = None


class FeedbackRequest(BaseModel):
    score: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = None


class MessageResponse(BaseModel):
    message: str


class DocumentItem(BaseModel):
    id: int
    original_filename: str | None
    document_title: str | None
    document_number: str | None
    document_type: str | None
    status: str
    processing_status: str
    review_status: str
    page_count: int | None
    summary_count: int
    created_at: datetime
    processed_at: datetime | None


class DocumentsResponse(BaseModel):
    items: list[DocumentItem]
    total: int
    page: int
    page_size: int


class ChunkItem(BaseModel):
    id: int
    chunk_index: int | None
    section_code: str | None
    page_number: int | None
    start_line: int | None
    end_line: int | None
    content_preview: str | None
    citation: dict[str, Any] | None


class SummaryItem(BaseModel):
    id: int
    document_id: int
    title: str | None
    version_no: int
    summary_text: str | None
    model_name: str | None
    groundedness_score: float | None
    is_reviewed: bool
    feedback_score: int | None
    created_at: datetime


class DocumentDetailResponse(BaseModel):
    id: int
    original_filename: str | None
    file_path: str | None
    document_title: str | None
    document_number: str | None
    document_type: str | None
    page_count: int | None
    status: str
    processing_status: str
    review_status: str
    clean_text: str | None
    classification_label: str | None
    classification_score: float | None
    structure: dict[str, Any] | None
    page_index: list[dict[str, Any]] | None
    chunks: list[ChunkItem]
    summaries: list[SummaryItem]
    created_at: datetime
    processed_at: datetime | None


class HistoryResponse(BaseModel):
    items: list[SummaryItem]
    total: int
    page: int
    page_size: int


@router.get("/supported-formats")
async def supported_formats() -> dict[str, list[str]]:
    return {"formats": get_supported_formats()}


@router.get("/health/ollama")
async def ollama_health(current_user: User = Depends(require_active_user)) -> dict[str, Any]:
    del current_user
    return await check_ollama_health()


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    auto_summary: bool = False,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    file_bytes = await file.read()
    document, summary = await upload_document(
        db,
        current_user=current_user,
        file_bytes=file_bytes,
        original_filename=file.filename,
        mime_type=file.content_type,
        auto_summary=auto_summary,
    )
    return {
        "document": _serialize_document(document),
        "summary": _serialize_summary(summary) if summary else None,
    }


@router.get("/documents", response_model=DocumentsResponse)
async def get_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    document_type: str | None = None,
    processing_status: str | None = None,
    review_status: str | None = None,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> DocumentsResponse:
    items, total = list_documents(
        db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        search=search,
        document_type=document_type,
        processing_status=processing_status,
        review_status=review_status,
    )
    return DocumentsResponse(items=[_serialize_document(item) for item in items], total=total, page=page, page_size=page_size)


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> DocumentDetailResponse:
    return _serialize_document_detail(get_document_detail(db, document_id, current_user))


@router.delete("/documents/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: int,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    payload = delete_document_cascade(db, document_id=document_id, current_user=current_user)
    return MessageResponse(message=f"Deleted document {payload['document_id']}")


@router.post("/summarize")
async def summarize(
    payload: SummarizeRequest,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.document_id is not None:
        summary = await create_summary_for_document(
            db,
            document_id=payload.document_id,
            current_user=current_user,
            title=payload.title,
        )
        return {"mode": "document_summary", "summary": _serialize_summary(summary)}
    if payload.query:
        result = await answer_question(
            db,
            current_user=current_user,
            query=payload.query,
            top_k=payload.top_k,
            document_ids=payload.document_ids,
        )
        return {"mode": "rag_answer", **result}
    return {"mode": "noop", "message": "Provide either document_id or query"}


@router.post("/search")
async def search(
    payload: QueryRequest,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "query": payload.query,
        "results": search_chunks(
            db,
            current_user=current_user,
            query=payload.query,
            top_k=payload.top_k,
            document_ids=payload.document_ids,
        ),
    }


@router.get("/history", response_model=HistoryResponse)
async def history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    document_id: int | None = None,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> HistoryResponse:
    items, total = list_history(
        db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        document_id=document_id,
    )
    return HistoryResponse(items=[_serialize_summary(item) for item in items], total=total, page=page, page_size=page_size)


@router.get("/summaries/{summary_id}")
async def summary_detail(
    summary_id: int,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"summary": _serialize_summary(get_summary_detail(db, summary_id, current_user))}


@router.post("/summaries/{summary_id}/review", response_model=SummaryItem)
async def review(
    summary_id: int,
    payload: ReviewRequest,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> SummaryItem:
    return _serialize_summary(
        review_summary(
            db,
            summary_id=summary_id,
            current_user=current_user,
            approved=payload.approved,
            note=payload.note,
        )
    )


@router.post("/summaries/{summary_id}/feedback", response_model=SummaryItem)
async def feedback(
    summary_id: int,
    payload: FeedbackRequest,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> SummaryItem:
    return _serialize_summary(
        leave_summary_feedback(
            db,
            summary_id=summary_id,
            current_user=current_user,
            score=payload.score,
            comment=payload.comment,
        )
    )


@router.get("/summaries/{summary_id}/export")
async def export(
    summary_id: int,
    format: str = Query(default="txt"),
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    export_path = export_summary(
        db,
        summary_id=summary_id,
        current_user=current_user,
        export_format=format,
    )
    media_type = {
        "txt": "text/plain",
        "json": "application/json",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(format.lower(), "application/octet-stream")
    return FileResponse(Path(export_path), media_type=media_type, filename=Path(export_path).name)


def _serialize_document(item: Document) -> DocumentItem:
    return DocumentItem(
        id=item.id,
        original_filename=item.original_filename,
        document_title=item.document_title,
        document_number=item.document_number,
        document_type=item.document_type,
        status=item.status,
        processing_status=item.processing_status,
        review_status=item.review_status,
        page_count=item.page_count,
        summary_count=len(item.summaries or []),
        created_at=item.created_at,
        processed_at=item.processed_at,
    )


def _serialize_summary(item: SummaryHistory) -> SummaryItem:
    groundedness = float(item.groundedness_score) if item.groundedness_score is not None else None
    return SummaryItem(
        id=item.id,
        document_id=item.document_id,
        title=item.title,
        version_no=item.version_no,
        summary_text=item.summary_text,
        model_name=item.model_name,
        groundedness_score=groundedness,
        is_reviewed=item.is_reviewed,
        feedback_score=item.feedback_score,
        created_at=item.created_at,
    )


def _serialize_document_detail(item: Document) -> DocumentDetailResponse:
    return DocumentDetailResponse(
        id=item.id,
        original_filename=item.original_filename,
        file_path=item.file_path,
        document_title=item.document_title,
        document_number=item.document_number,
        document_type=item.document_type,
        page_count=item.page_count,
        status=item.status,
        processing_status=item.processing_status,
        review_status=item.review_status,
        clean_text=item.clean_text,
        classification_label=item.classification_label,
        classification_score=float(item.classification_score) if item.classification_score is not None else None,
        structure=_json_load(item.structure_json),
        page_index=_json_load(item.page_index_json),
        chunks=[
            ChunkItem(
                id=chunk.id,
                chunk_index=chunk.chunk_index,
                section_code=chunk.section_code,
                page_number=chunk.page_number,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content_preview=chunk.content_preview,
                citation=_json_load(chunk.citation_json),
            )
            for chunk in sorted(item.chunks, key=lambda value: value.chunk_index or 0)
        ],
        summaries=[_serialize_summary(summary) for summary in sorted(item.summaries, key=lambda value: value.version_no)],
        created_at=item.created_at,
        processed_at=item.processed_at,
    )


def _json_load(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
