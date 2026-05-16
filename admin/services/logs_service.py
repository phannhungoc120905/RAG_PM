import json
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any
from fastapi import HTTPException
from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session
from config import settings
from db.models import (
    SystemLog, LoginHistory, User, PermissionGroup, SystemFunction, PermissionGroupFunction,
    IssuingUnit, Department, Position, SystemConfig, Document, ChunkMetadata,
    SummaryHistory, WorkAssignmentDocument, WorkItem, NoticeDocument, APIKey
)

SNAPSHOT_MODELS = [
    PermissionGroup,
    SystemFunction,
    PermissionGroupFunction,
    User,
    IssuingUnit,
    Department,
    Position,
    User,
    LoginHistory,
    SystemConfig,
    Document,
    ChunkMetadata,
    SummaryHistory,
    WorkAssignmentDocument,
    WorkItem,
    NoticeDocument,
    SystemLog,
    APIKey,
]

SNAPSHOT_DELETE_ORDER = [
    PermissionGroupFunction,
    APIKey,
    SystemLog,
    Document,
    User,
    WorkItem,
    NoticeDocument,
    WorkAssignmentDocument,
    SummaryHistory,
    ChunkMetadata,
    Document,
    LoginHistory,
    SystemConfig,
    User,
    Position,
    Department,
    IssuingUnit,
    SystemFunction,
    PermissionGroup,
]

def list_logs(
    db: Session,
    page: int,
    page_size: int,
    user_id: int | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[SystemLog], int]:
    statement: Select[tuple[SystemLog]] = select(SystemLog)
    count_statement = select(func.count()).select_from(SystemLog)

    if user_id is not None:
        statement = statement.where(SystemLog.user_id == user_id)
        count_statement = count_statement.where(SystemLog.user_id == user_id)
    if action:
        statement = statement.where(SystemLog.action.ilike(f"%{action}%"))
        count_statement = count_statement.where(SystemLog.action.ilike(f"%{action}%"))
    if date_from:
        statement = statement.where(SystemLog.created_at >= date_from)
        count_statement = count_statement.where(SystemLog.created_at >= date_from)
    if date_to:
        statement = statement.where(SystemLog.created_at <= date_to)
        count_statement = count_statement.where(SystemLog.created_at <= date_to)

    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(SystemLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all())
    return items, total

def list_login_history(
    db: Session,
    page: int,
    page_size: int,
    search: str | None = None,
    user_id: int | None = None,
    login_type: str | None = None,
    status_value: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[LoginHistory], int]:
    from sqlalchemy.orm import selectinload
    statement: Select[tuple[LoginHistory]] = select(LoginHistory).options(selectinload(LoginHistory.user))
    count_statement = select(func.count()).select_from(LoginHistory)

    if search:
        statement = statement.where(LoginHistory.username_snapshot.ilike(f"%{search}%"))
        count_statement = count_statement.where(LoginHistory.username_snapshot.ilike(f"%{search}%"))
    if user_id is not None:
        statement = statement.where(LoginHistory.user_id == user_id)
        count_statement = count_statement.where(LoginHistory.user_id == user_id)
    if login_type:
        statement = statement.where(LoginHistory.login_type == login_type)
        count_statement = count_statement.where(LoginHistory.login_type == login_type)
    if status_value:
        statement = statement.where(LoginHistory.status == status_value)
        count_statement = count_statement.where(LoginHistory.status == status_value)
    if date_from:
        statement = statement.where(LoginHistory.login_at >= date_from)
        count_statement = count_statement.where(LoginHistory.login_at >= date_from)
    if date_to:
        statement = statement.where(LoginHistory.login_at <= date_to)
        count_statement = count_statement.where(LoginHistory.login_at <= date_to)

    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(LoginHistory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all())
    return items, total

def export_logs_to_excel(
    db: Session,
    user_id: int | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Path:
    from openpyxl import Workbook
    logs, _ = list_logs(db, 1, 100000, user_id, action, date_from, date_to)

    export_dir = Path(settings.BACKUP_DIR) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"system_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    workbook = Workbook()
    sheet = workbook.active or workbook.create_sheet("system_logs", 0)
    sheet.title = "system_logs"
    sheet.append(["id", "user_id", "action", "detail", "ip_address", "status_code", "created_at"])
    for item in logs:
        sheet.append(
            [
                item.id,
                item.user_id,
                item.action,
                item.detail,
                item.ip_address,
                item.status_code,
                item.created_at.isoformat() if item.created_at else None,
            ]
        )
    workbook.save(export_path)
    return export_path

def write_system_log(
    db: Session,
    action: str,
    status_code: int,
    user_id: int | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        SystemLog(
            user_id=user_id,
            action=action,
            detail=detail,
            ip_address=ip_address,
            status_code=status_code,
        )
    )
    db.commit()

def create_backup(db: Session, actor_user_id: int) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = Path(settings.BACKUP_DIR) / timestamp
    backup_root.mkdir(parents=True, exist_ok=True)

    snapshot = _build_db_snapshot(db)
    snapshot_path = backup_root / "db_snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    copied_items = [snapshot_path]
    db_dump_path = Path("db_dump.sql")
    if db_dump_path.exists():
        destination = backup_root / db_dump_path.name
        shutil.copy2(db_dump_path, destination)
        copied_items.append(destination)

    faiss_path = Path(settings.FAISS_INDEX_PATH)
    if faiss_path.exists():
        destination = backup_root / faiss_path.name
        shutil.copytree(faiss_path, destination, dirs_exist_ok=True)
        copied_items.append(destination)

    metadata = {
        "backup_name": timestamp,
        "backup_path": str(backup_root),
        "created_at": datetime.now().isoformat(),
        "created_by": actor_user_id,
        "has_db_snapshot": True,
        "has_db_dump": db_dump_path.exists(),
        "has_faiss_index": faiss_path.exists(),
    }
    (backup_root / "backup_meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    size_kb = round(sum(_path_size(item) for item in copied_items) / 1024, 2)
    write_system_log(
        db,
        action="manual_backup",
        status_code=200,
        user_id=actor_user_id,
        detail=json.dumps(metadata, ensure_ascii=False),
    )
    return {
        "backup_name": timestamp,
        "backup_path": str(backup_root),
        "created_at": metadata["created_at"],
        "size_kb": size_kb,
        "has_db_dump": metadata["has_db_dump"],
        "has_faiss_index": metadata["has_faiss_index"],
    }

def list_backups() -> list[dict[str, Any]]:
    backup_dir = Path(settings.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for entry in sorted(backup_dir.iterdir(), reverse=True):
        if not entry.is_dir():
            continue
        meta_path = entry / "backup_meta.json"
        if meta_path.exists():
            items.append(json.loads(meta_path.read_text(encoding="utf-8")))
        else:
            items.append(
                {
                    "backup_name": entry.name,
                    "backup_path": str(entry),
                    "created_at": datetime.fromtimestamp(entry.stat().st_mtime).isoformat(),
                    "has_db_snapshot": (entry / "db_snapshot.json").exists(),
                    "has_db_dump": (entry / "db_dump.sql").exists(),
                    "has_faiss_index": (entry / Path(settings.FAISS_INDEX_PATH).name).exists(),
                }
            )
    return items

def restore_backup(
    db: Session,
    backup_name: str,
    actor_user_id: int,
) -> dict[str, Any]:
    backup_root = Path(settings.BACKUP_DIR) / backup_name
    if not backup_root.exists():
        raise HTTPException(status_code=404, detail="Backup not found")

    snapshot_path = backup_root / "db_snapshot.json"
    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail="Backup snapshot not found")

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    _restore_db_snapshot(db, snapshot)

    backup_faiss = backup_root / Path(settings.FAISS_INDEX_PATH).name
    if backup_faiss.exists():
        target = Path(settings.FAISS_INDEX_PATH)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(backup_faiss, target)

    backup_dump = backup_root / "db_dump.sql"
    if backup_dump.exists():
        shutil.copy2(backup_dump, Path("db_dump.sql"))

    detail = {
        "backup_name": backup_name,
        "restored_at": datetime.now().isoformat(),
    }
    write_system_log(
        db,
        action="restore_backup",
        status_code=200,
        user_id=actor_user_id,
        detail=json.dumps(detail, ensure_ascii=False),
    )
    return detail

def _build_db_snapshot(db: Session) -> dict[str, list[dict[str, Any]]]:
    snapshot: dict[str, list[dict[str, Any]]] = {}
    for model in SNAPSHOT_MODELS:
        rows = db.scalars(select(model)).all()
        snapshot[model.__tablename__] = [_serialize_model_row(model, row) for row in rows]
    return snapshot

def _restore_db_snapshot(db: Session, snapshot: dict[str, list[dict[str, Any]]]) -> None:
    for model in SNAPSHOT_DELETE_ORDER:
        db.execute(delete(model))
    db.commit()
    for model in SNAPSHOT_MODELS:
        rows = snapshot.get(model.__tablename__, [])
        if not rows:
            continue
        restored_rows = [_deserialize_model_row(model, row) for row in rows]
        db.execute(model.__table__.insert(), restored_rows)
    db.commit()

def _serialize_model_row(model: type, row: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in model.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, (datetime, date)):
            data[column.name] = value.isoformat()
        else:
            data[column.name] = value
    return data

def _deserialize_model_row(model: type, row: dict[str, Any]) -> dict[str, Any]:
    restored: dict[str, Any] = {}
    for column in model.__table__.columns:
        value = row.get(column.name)
        if value is None:
            restored[column.name] = None
            continue
        try:
            python_type = column.type.python_type
        except (AttributeError, NotImplementedError):
            python_type = None
        if python_type is datetime and isinstance(value, str):
            restored[column.name] = datetime.fromisoformat(value)
        elif python_type is date and isinstance(value, str):
            restored[column.name] = date.fromisoformat(value)
        else:
            restored[column.name] = value
    return restored

def _path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
