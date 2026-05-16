import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from fastapi import HTTPException
from sqlalchemy import Select, func, select, or_
from sqlalchemy.orm import Session
from config import settings
from db.models import SystemConfig, User, Document, SummaryHistory
from admin.services.common import _get_config_or_404

def get_system_status(db: Session) -> dict[str, Any]:
    upload_dir = Path(settings.UPLOAD_DIR)
    disk_target = upload_dir if upload_dir.exists() else Path(".")
    usage = shutil.disk_usage(disk_target)

    return {
        "disk": {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
        },
        "uploads": {
            "processing_count": _count_files(upload_dir / "processing"),
            "done_count": _count_files(upload_dir / "done"),
            "failed_count": _count_files(upload_dir / "failed"),
        },
        "db": {
            "users_count": db.scalar(select(func.count()).select_from(User)) or 0,
            "documents_count": db.scalar(select(func.count()).select_from(Document)) or 0,
            "summaries_count": db.scalar(select(func.count()).select_from(SummaryHistory)) or 0,
        },
        "app": {
            "version": "1.0.0",
            "debug": settings.DEBUG,
        },
    }

def list_system_configs(
    db: Session,
    page: int,
    page_size: int,
    search: str | None,
    category: str | None,
) -> tuple[list[SystemConfig], int]:
    statement: Select[tuple[SystemConfig]] = select(SystemConfig)
    count_statement = select(func.count()).select_from(SystemConfig)

    if search:
        criteria = or_(
            SystemConfig.config_key.ilike(f"%{search}%"),
            SystemConfig.description.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    if category:
        statement = statement.where(SystemConfig.category == category)
        count_statement = count_statement.where(SystemConfig.category == category)

    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(SystemConfig.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all())
    return items, total

def create_system_config(
    db: Session,
    actor_user_id: int,
    payload: dict[str, Any],
) -> SystemConfig:
    if db.scalar(select(SystemConfig).where(SystemConfig.config_key == payload["config_key"])):
        raise HTTPException(status_code=409, detail="Config key already exists")

    config = SystemConfig(
        config_key=payload["config_key"],
        config_value=str(payload["config_value"]),
        category=payload.get("category", "general"),
        data_type=payload.get("data_type", "string"),
        description=payload.get("description"),
        is_active=payload.get("is_active", True),
        updated_by=actor_user_id,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    _sync_config_to_settings(config.config_key, config.config_value, config.data_type)
    return config

def update_system_config(
    db: Session,
    config_id: int,
    actor_user_id: int,
    payload: dict[str, Any],
) -> SystemConfig:
    config = _get_config_or_404(db, config_id)
    if "config_key" in payload and payload["config_key"] != config.config_key:
        if db.scalar(select(SystemConfig).where(SystemConfig.config_key == payload["config_key"])):
            raise HTTPException(status_code=409, detail="Config key already exists")
    for field in ("config_key", "config_value", "category", "data_type", "description", "is_active"):
        if field in payload:
            setattr(config, field, str(payload[field]) if field == "config_value" else payload[field])
    config.updated_by = actor_user_id
    config.updated_at = datetime.utcnow()
    db.add(config)
    db.commit()
    db.refresh(config)
    _sync_config_to_settings(config.config_key, config.config_value, config.data_type)
    return config

def delete_system_config(db: Session, config_id: int) -> None:
    config = _get_config_or_404(db, config_id)
    db.delete(config)
    db.commit()

def get_safe_config() -> dict[str, Any]:
    return {
        "model_name": settings.MODEL_NAME,
        "model_path": settings.MODEL_PATH,
        "faiss_index_path": settings.FAISS_INDEX_PATH,
        "vector_dim": settings.VECTOR_DIM,
        "chunk_size": settings.CHUNK_SIZE,
        "chunk_overlap": settings.CHUNK_OVERLAP,
        "ocr_lang": settings.OCR_LANG,
    }

def update_runtime_config(payload: dict[str, Any]) -> dict[str, Any]:
    for field in ("model_name", "chunk_size", "chunk_overlap"):
        if field in payload:
            setattr(settings, field.upper(), payload[field])
    return get_safe_config()

def _sync_config_to_settings(config_key: str, config_value: str, data_type: str) -> None:
    mapping = {
        "MODEL_NAME": "MODEL_NAME",
        "MODEL_PATH": "MODEL_PATH",
        "FAISS_INDEX_PATH": "FAISS_INDEX_PATH",
        "VECTOR_DIM": "VECTOR_DIM",
        "CHUNK_SIZE": "CHUNK_SIZE",
        "CHUNK_OVERLAP": "CHUNK_OVERLAP",
        "OCR_LANG": "OCR_LANG",
        "UPLOAD_DIR": "UPLOAD_DIR",
        "MAX_FILE_SIZE_MB": "MAX_FILE_SIZE_MB",
        "BACKUP_DIR": "BACKUP_DIR",
        "SSO_ENABLED": "SSO_ENABLED",
        "SSO_PROVIDER_NAME": "SSO_PROVIDER_NAME",
        "SSO_SHARED_SECRET": "SSO_SHARED_SECRET",
        "SSO_AUTO_CREATE_USERS": "SSO_AUTO_CREATE_USERS",
    }
    setting_name = mapping.get(config_key.upper())
    if not setting_name:
        return

    value: Any = config_value
    normalized_type = data_type.lower()
    if normalized_type == "int":
        value = int(config_value)
    elif normalized_type == "bool":
        value = config_value.lower() in {"1", "true", "yes", "on"}
    setattr(settings, setting_name, value)

def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.iterdir() if item.is_file())
