from datetime import date, datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from db.database import get_db
from auth.dependencies import require_action
from db.models import User
from admin.service import (
    list_logs,
    list_login_history,
    export_logs_to_excel,
    list_backups,
    create_backup,
    restore_backup
)
from admin.schemas import (
    LogsResponse,
    LogItem,
    LoginHistoryResponse,
    LoginHistoryItem,
    BackupItem,
    BackupResponse,
    RestoreBackupResponse,
    MessageResponse
)

router = APIRouter(tags=["Logs & Backups"])

@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int | None = None,
    action: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(require_action("admin.logs.list")),
    db: Session = Depends(get_db),
) -> LogsResponse:
    items, total = list_logs(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        action=action,
        date_from=datetime.combine(date_from, datetime.min.time()) if date_from else None,
        date_to=datetime.combine(date_to, datetime.max.time()) if date_to else None,
    )
    return LogsResponse(
        items=[
            LogItem(
                id=item.id,
                user_id=item.user_id,
                action=item.action,
                detail=item.detail,
                ip_address=item.ip_address,
                status_code=item.status_code,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.get("/login-history", response_model=LoginHistoryResponse)
async def get_login_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    user_id: int | None = None,
    login_type: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(require_action("admin.login_history.list")),
    db: Session = Depends(get_db),
) -> LoginHistoryResponse:
    items, total = list_login_history(
        db,
        page=page,
        page_size=page_size,
        search=search,
        user_id=user_id,
        login_type=login_type,
        status_value=status,
        date_from=datetime.combine(date_from, datetime.min.time()) if date_from else None,
        date_to=datetime.combine(date_to, datetime.max.time()) if date_to else None,
    )
    return LoginHistoryResponse(
        items=[
            LoginHistoryItem(
                id=item.id,
                user_id=item.user_id,
                username_snapshot=item.username_snapshot,
                login_type=item.login_type,
                session_id=item.session_id,
                login_at=item.login_at,
                logout_at=item.logout_at,
                status=item.status,
                ip_address=item.ip_address,
                detail=item.detail,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.get("/logs/export")
async def export_logs(
    current_user: User = Depends(require_action("admin.logs.export")),
    db: Session = Depends(get_db),
):
    filepath = export_logs_to_excel(db)
    return FileResponse(
        filepath,
        filename=f"system_logs_{date.today()}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@router.get("/backups", response_model=list[BackupItem])
async def get_backups(
    current_user: User = Depends(require_action("admin.backups.list")),
) -> list[BackupItem]:
    return list_backups()

@router.post("/backups", response_model=BackupResponse)
async def add_backup(
    current_user: User = Depends(require_action("admin.backups.create")),
    db: Session = Depends(get_db),
) -> BackupResponse:
    return create_backup(db, actor_user_id=int(current_user.id))

@router.post("/backups/restore", response_model=RestoreBackupResponse)
async def restore(
    backup_name: str,
    current_user: User = Depends(require_action("admin.backups.restore")),
    db: Session = Depends(get_db),
) -> RestoreBackupResponse:
    return restore_backup(
        db,
        backup_name=backup_name,
        actor_user_id=int(current_user.id),
    )
