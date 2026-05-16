from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from admin.routers import user, security, system, work, entities, logs

router = APIRouter()

# --- UI Routes ---
TEMPLATES_DIR = Path("templates")

def read_html_file(filename: str, fallback: str) -> str:
    path = TEMPLATES_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback

@router.get("/", response_class=HTMLResponse, tags=["UI"])
async def admin_root_page() -> str:
    return read_html_file("admin_master.html", "<h1>Admin Master</h1>")

@router.get("/dashboard", response_class=HTMLResponse, tags=["UI"])
async def admin_dashboard_page() -> str:
    return read_html_file("admin_master.html", "<h1>Admin Dashboard</h1>")

@router.get("/users-ui", response_class=HTMLResponse, tags=["UI"])
async def admin_users_page() -> str:
    return read_html_file("admin_master.html", "<h1>Admin Master</h1>")

@router.get("/system-config-ui", response_class=HTMLResponse, tags=["UI"])
async def admin_system_config_page() -> str:
    return read_html_file("admin_master.html", "<h1>Admin Master</h1>")

@router.get("/login", response_class=HTMLResponse, tags=["UI"])
async def admin_login_page() -> str:
    return read_html_file("admin_login_new.html", "<h1>Login Page</h1>")

# --- Include Domain Routers ---
router.include_router(user.router)
router.include_router(security.router)
router.include_router(system.router)
router.include_router(work.router)
router.include_router(entities.router)
router.include_router(logs.router)
