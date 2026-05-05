from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import HTMLResponse
from ocr.service import OCRService
from pydantic import BaseModel
from typing import List, Dict, Any
import logging

router = APIRouter(prefix="/ocr", tags=["OCR"])
ocr_service = OCRService()
logger = logging.getLogger(__name__)


def read_html_file(filename: str, fallback: str) -> str:
    path = Path(filename)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


@router.get("/ui", response_class=HTMLResponse)
async def ocr_page() -> str:
    return read_html_file("ocr_processing.html", "<h1>OCR Processing</h1>")

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5

@router.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    """
    Endpoint to extract text from images or PDFs.
    Supports Vietnamese and English.
    """
    try:
        content = await file.read()
        text = ocr_service.process_file(content, file.filename)
        return {"filename": file.filename, "text": text}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/upload-process")
async def upload_and_process(file: UploadFile = File(...)):
    """
    Flow: OCR -> Normalize -> Chunk -> Embedding -> Store
    """
    try:
        # 1. OCR
        content = await file.read()
        raw_text = ocr_service.process_file(content, file.filename)
        
        # 2. Normalize
        clean_text = ocr_service.normalize_text(raw_text)
        
        # 3. Chunk
        chunks = ocr_service.chunk_text(clean_text)
        if not chunks:
            return {"status": "success", "message": "No text detected to process", "chunks_count": 0}
            
        # 4. Embedding
        embedded_chunks = ocr_service.embed_chunks(chunks)
        
        # 5. Store
        ocr_service.store_embeddings(embedded_chunks)
        
        return {
            "status": "success", 
            "filename": file.filename, 
            "chunks_count": len(chunks)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal processing error")

@router.post("/search")
async def search_chunks(request: QueryRequest):
    """
    Perform hybrid search (BM25 + Vector)
    """
    try:
        results = ocr_service.hybrid_search(request.query, top_k=request.top_k)
        return {"query": request.query, "results": results}
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")

@router.post("/summarize")
async def summarize_ask(request: QueryRequest):
    """
    RAG Pipeline: Hybrid Search + LLM Answer
    """
    try:
        result = await ocr_service.get_rag_answer(request.query, top_k=request.top_k)
        return result
    except Exception as e:
        logger.error(f"RAG error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate answer")
