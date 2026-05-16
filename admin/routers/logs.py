from datetime import date, datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from db.database import get_db
from auth.dependencies import require_admin
from admin.service import (
    list_logs,
    export_logs_to_excel,
    list_backups,
    create_backup,
    restore_backup
)
from admin.schemas import (
    LogsResponse,
    LogItem,
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
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LogsResponse:
    del admin_user
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

@router.get("/logs/export")
async def export_logs(
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    del admin_user
    filepath = export_logs_to_excel(db)
    return FileResponse(
        filepath,
        filename=f"system_logs_{date.today()}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@router.get("/backups", response_model=list[BackupItem])
async def get_backups(
    admin_user: dict = Depends(require_admin),
) -> list[BackupItem]:
    del admin_user
    return list_backups()

@router.post("/backups", response_model=BackupResponse)
async def add_backup(
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BackupResponse:
    return create_backup(db, actor_user_id=int(admin_user["sub"]))

@router.post("/backups/restore", response_model=RestoreBackupResponse)
async def restore(
    backup_name: str,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RestoreBackupResponse:
    return restore_backup(
        db,
        backup_name=backup_name,
        actor_user_id=int(admin_user["sub"]),
    )
