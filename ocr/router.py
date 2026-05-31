import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from auth.dependencies import require_action
from db.models import User
from ocr.runtime import ocr_service
from config import settings


router = APIRouter(prefix="/ocr", tags=["OCR"])
logger = logging.getLogger(__name__)
TEMPLATES_DIR = Path("templates")


def read_html_file(filename: str, fallback: str) -> str:
    path = TEMPLATES_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback

class QueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class TextAnalyzeRequest(BaseModel):
    text: str


@router.get("/ui", response_class=HTMLResponse)
async def ocr_page() -> str:
    return read_html_file("ocr_processing.html", "<h1>OCR Processing</h1>")


@router.get("/supported-formats")
async def supported_formats(
    current_user: User = Depends(require_action("ocr.supported_formats.view")),
) -> dict[str, list[str]]:
    del current_user
    return {
        "formats": ["pdf", "docx", "txt", "jpg", "jpeg", "png", "bmp", "tif", "tiff"],
    }


@router.post("/extract-text")
async def extract_text(
    file: UploadFile = File(...),
    fix_with_ai: bool = Query(default=False),
    current_user: User = Depends(require_action("ocr.extract_text.create")),
):
    """
    Endpoint to extract text from images or PDFs.
    Supports Vietnamese and English.
    """
    try:
        content = await file.read()
        text = ocr_service.process_file(content, file.filename)
        
        if fix_with_ai:
            text = await ocr_service.fix_ocr_errors_with_llm(text)
            
        return {"filename": file.filename, "text": text}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    fix_with_ai: bool = Query(default=False),
    current_user: User = Depends(require_action("ocr.analyze.create")),
) -> dict[str, Any]:
    try:
        content = await file.read()
        result = ocr_service.process_document(content, file.filename)
        if fix_with_ai and getattr(ocr_service, "fix_processed_result_with_llm", None):
            result = await ocr_service.fix_processed_result_with_llm(result)
        return {
            "status": "success",
            "filename": result["filename"],
            "extension": result["extension"],
            "page_count": result["page_count"],
            "page_index": result["page_index"],
            "classification": result["classification"],
            "structure": result["structure"],
            "chunks_count": len(result["chunks"]),
            "chunks": result["chunks"],
            "text": result["clean_text"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Analyze error for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"Analyze failed: {exc}")


@router.post("/analyze-text")
async def analyze_text(
    payload: TextAnalyzeRequest,
    current_user: User = Depends(require_action("ocr.analyze_text.create")),
) -> dict[str, Any]:
    normalized = ocr_service.normalize_text(payload.text)
    chunks = ocr_service.chunk_text(normalized)
    return {
        "text": normalized,
        "classification": ocr_service.classify_document(normalized),
        "structure": ocr_service.detect_document_structure(normalized),
        "chunks_count": len(chunks),
        "chunks": chunks,
    }


@router.post("/upload-process")
async def upload_and_process(
    file: UploadFile = File(...),
    fix_with_ai: bool = Query(default=False),
    current_user: User = Depends(require_action("ocr.upload_process.create")),
):
    """
    Flow: OCR -> Normalize -> Chunk -> Embedding -> Store
    """
    try:
        content = await file.read()
        result = ocr_service.process_document(content, file.filename)
        raw_text = ocr_service.process_file(content, file.filename)
        
        # 2. Fix with AI if requested
        if fix_with_ai:
            raw_text = await ocr_service.fix_ocr_errors_with_llm(raw_text)
            
        # 3. Normalize
        clean_text = ocr_service.normalize_text(raw_text)
        
        # 4. Chunk
        chunks = ocr_service.chunk_text(clean_text)
        if not chunks:
            return {
                "status": "success",
                "message": "No text detected to process",
                "filename": file.filename,
                "page_count": result["page_count"],
                "classification": result["classification"],
                "structure": result["structure"],
                "chunks_count": 0,
            }

        embedded_chunks = ocr_service.embed_chunks(chunks)
        ocr_service.store_embeddings(embedded_chunks)

        return {
            "status": "success",
            "filename": file.filename,
            "page_count": result["page_count"],
            "page_index": result["page_index"],
            "classification": result["classification"],
            "structure": result["structure"],
            "chunks_count": len(chunks),
            "text": clean_text,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Processing error for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"Internal processing error: {exc}")

@router.post("/search")
async def search_chunks(
    request: QueryRequest,
    current_user: User = Depends(require_action("ocr.search.create")),
) -> dict[str, Any]:
    try:
        results = ocr_service.hybrid_search(request.query, top_k=request.top_k)
        return {
            "query": request.query,
            "results": results,
        }
    except Exception as exc:
        logger.exception("Search error for query=%s", request.query)
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")


@router.post("/summarize")
async def summarize_ask(
    request: QueryRequest,
    current_user: User = Depends(require_action("ocr.summarize.create")),
) -> dict[str, Any]:
    try:
        result = await ocr_service.get_rag_answer(request.query, top_k=request.top_k)
        return result
    except Exception as exc:
        logger.exception("RAG error for query=%s", request.query)
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {exc}")
