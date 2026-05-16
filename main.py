from admin.router import TEMPLATES_DIR
from api.service import log
from db.database import Base, engine, get_db
from db.models import User
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

# Import routers
from admin.router import router as admin_router
from api.router import router as api_router
from auth.router import router as auth_router
from ocr.router import router as ocr_router

# Import logic & config
from api.service import upload_document, get_latest_history_public
from auth.dependencies import require_active_user
from auth.middleware import add_middlewares
from config import settings
@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Khởi tạo CSDL
    Base.metadata.create_all(bind=engine)
    
    # Khởi tạo thư mục upload
    for stage in ["processing", "done", "failed"]:
        (Path(settings.UPLOAD_DIR) / stage).mkdir(parents=True, exist_ok=True)
    Path(settings.BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    
    log.info("app_started", extra={"env": "debug" if settings.DEBUG else "production"})
    yield

app = FastAPI(
    title="RAG_PM API",
    description="Hệ thống AI tóm tắt văn bản hành chính",
    version="1.0.0",
    lifespan=lifespan,
)

# Cấu hình Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
add_middlewares(app)

# Include Routers
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])
app.include_router(api_router, prefix="/api", tags=["AI"])
app.include_router(ocr_router, tags=["OCR"])

# --- UI Routes ---
def read_html_file(filename: str, fallback: str) -> str:
    path = TEMPLATES_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    # Fallback nếu không tìm thấy trong templates/ thì tìm ở gốc dự án
    root_path = Path(filename)
    if root_path.exists():
        return root_path.read_text(encoding="utf-8")
    return fallback

@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/admin/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return read_html_file("admin_login_new.html", "<h1>Login</h1>")

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=settings.DEBUG)
