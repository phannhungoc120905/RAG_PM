import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from ocr.router import router as ocr_router

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from admin.router import router as admin_router
from api.router import router as api_router
from auth.middleware import add_middlewares
from auth.router import router as auth_router
from config import settings
from logger import get_logger

log = get_logger("app.main")
HISTORY_FILE = "history.json"


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

app.include_router(ocr_router)
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])
app.include_router(api_router, prefix="/api", tags=["AI"])

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
    from langchain_ollama import OllamaLLM
    from langchain_core.prompts import ChatPromptTemplate

    # Tối ưu: Không dùng RAG (FAISS/Retrieval) cho việc tóm tắt văn bản đơn lẻ để tăng tốc độ
    # Chỉ sử dụng LLM trực tiếp với prompt tối ưu cho tiếng Việt
    llm = OllamaLLM(model=settings.MODEL_NAME, temperature=0.3)
    
    prompt = ChatPromptTemplate.from_template(
        """
        ### Hệ thống: Bạn là chuyên gia tóm tắt văn bản hành chính Việt Nam.
        ### Nhiệm vụ: Tóm tắt nội dung dưới đây một cách ngắn gọn, súc tích bằng tiếng Việt.
        ### Yêu cầu:
        1. Trình bày dưới dạng danh sách tối đa 5 gạch đầu dòng.
        2. Giữ nguyên các thông tin quan trọng như: Số hiệu, Ngày tháng, Tên cơ quan, Nội dung chính.
        3. Sử dụng ngôn ngữ hành chính chuẩn.

        NỘI DUNG VĂN BẢN:
        ---
        {context}
        ---
        BẢN TÓM TẮT TIẾNG VIỆT:
        """
    )
    
    # Sử dụng chuỗi xử lý trực tiếp để giảm latency
    chain = prompt | llm
    response = chain.invoke({"context": text})
    
    return response.strip()


def read_html_file(filename: str, fallback: str) -> str:
    path = Path(filename)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


@app.get("/", response_class=HTMLResponse)
async def admin_login_page() -> str:
    return read_html_file("admin_login.html", "<h1>RAG_PM Admin Login</h1>")


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard_page() -> str:
    return read_html_file("admin_dashboard.html", "<h1>RAG_PM Admin Dashboard</h1>")


@app.get("/summarizer", response_class=HTMLResponse)
async def summarizer_page() -> str:
    return read_html_file("index.html", "<h1>AI PDF Summarizer</h1>")


@app.get("/history")
async def history() -> list[dict]:
    return get_history()


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    temp_path = f"temp_{file.filename}"
    try:
        contents = await file.read()
        with open(temp_path, "wb") as temp_file:
            temp_file.write(contents)

        text = extract_text(temp_path)
        summary = summarize_with_ollama(text)
        save_to_history(file.filename, summary)
        return {"summary": summary}
    except Exception as exc:
        log.error(f"legacy_upload_failed: {file.filename} - Error: {str(exc)}")
        return {"error": str(exc)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=settings.DEBUG)
