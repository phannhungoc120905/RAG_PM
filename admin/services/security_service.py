import hashlib
import secrets
from datetime import datetime
from typing import Any
from fastapi import HTTPException
from sqlalchemy import Select, func, select, or_
from sqlalchemy.orm import Session, selectinload
from db.models import APIKey, PermissionGroup, SystemFunction, PermissionGroupFunction
from admin.services.common import _get_api_key_or_404, _get_group_or_404, _get_function_or_404

def list_api_keys(
    db: Session,
    page: int,
    page_size: int,
    search: str | None,
) -> tuple[list[APIKey], int]:
    statement: Select[tuple[APIKey]] = select(APIKey).options(selectinload(APIKey.creator))
    count_statement = select(func.count()).select_from(APIKey)

    if search:
        criteria = or_(
            APIKey.name.ilike(f"%{search}%"),
            APIKey.description.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)

    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(APIKey.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all())
    return items, total

def create_api_key(
    db: Session,
    actor_user_id: int,
    payload: dict[str, Any],
) -> tuple[APIKey, str]:
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    api_key = APIKey(
        name=payload["name"],
        description=payload.get("description"),
        key_hash=key_hash,
        created_by=actor_user_id,
        is_active=payload.get("is_active", True),
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key, raw_key

def update_api_key(db: Session, api_key_id: int, payload: dict[str, Any]) -> APIKey:
    api_key = _get_api_key_or_404(db, api_key_id)
    for field in ("name", "description", "is_active"):
        if field in payload:
            setattr(api_key, field, payload[field])
    api_key.updated_at = datetime.utcnow()
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key

def delete_api_key(db: Session, api_key_id: int) -> None:
    api_key = _get_api_key_or_404(db, api_key_id)
    db.delete(api_key)
    db.commit()

def list_permission_groups(
    db: Session,
    page: int,
    page_size: int,
    search: str | None,
) -> tuple[list[PermissionGroup], int]:
    statement: Select[tuple[PermissionGroup]] = select(PermissionGroup).options(
        selectinload(PermissionGroup.function_permissions).selectinload(
            PermissionGroupFunction.function
        )
    )
    count_statement = select(func.count()).select_from(PermissionGroup)

    if search:
        criteria = or_(
            PermissionGroup.name.ilike(f"%{search}%"),
            PermissionGroup.code.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)

    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(PermissionGroup.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all())
    return items, total

def create_permission_group(db: Session, payload: dict[str, Any]) -> PermissionGroup:
    if db.scalar(select(PermissionGroup).where(PermissionGroup.code == payload["code"])):
        raise HTTPException(status_code=409, detail="Permission group code already exists")

    group = PermissionGroup(
        name=payload["name"],
        code=payload["code"],
        description=payload.get("description"),
        is_active=payload.get("is_active", True),
    )
    db.add(group)
    db.flush()
    _replace_group_permissions(db, group, payload.get("permissions", []))
    db.commit()
    db.refresh(group)
    return group

def update_permission_group(
    db: Session,
    group_id: int,
    payload: dict[str, Any],
) -> PermissionGroup:
    group = _get_group_or_404(db, group_id)
    if "code" in payload and payload["code"] != group.code:
        if db.scalar(select(PermissionGroup).where(PermissionGroup.code == payload["code"])):
            raise HTTPException(status_code=409, detail="Permission group code already exists")
    for field in ("name", "code", "description", "is_active"):
        if field in payload:
            setattr(group, field, payload[field])
    if "permissions" in payload:
        _replace_group_permissions(db, group, payload["permissions"])
    group.updated_at = datetime.utcnow()
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

def delete_permission_group(db: Session, group_id: int) -> None:
    group = _get_group_or_404(db, group_id)
    if group.users:
        raise HTTPException(status_code=400, detail="Group is assigned to users")
    db.delete(group)
    db.commit()

def list_system_functions(
    db: Session,
    page: int,
    page_size: int,
    search: str | None,
) -> tuple[list[SystemFunction], int]:
    statement: Select[tuple[SystemFunction]] = select(SystemFunction)
    count_statement = select(func.count()).select_from(SystemFunction)

    if search:
        criteria = or_(
            SystemFunction.name.ilike(f"%{search}%"),
            SystemFunction.code.ilike(f"%{search}%"),
            SystemFunction.module.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)

    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(SystemFunction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all())
    return items, total

def create_system_function(db: Session, payload: dict[str, Any]) -> SystemFunction:
    if db.scalar(select(SystemFunction).where(SystemFunction.code == payload["code"])):
        raise HTTPException(status_code=409, detail="Function code already exists")

    function = SystemFunction(
        name=payload["name"],
        code=payload["code"],
        module=payload.get("module"),
        description=payload.get("description"),
        is_active=payload.get("is_active", True),
    )
    db.add(function)
    db.commit()
    db.refresh(function)
    return function

def update_system_function(
    db: Session,
    function_id: int,
    payload: dict[str, Any],
) -> SystemFunction:
    function = _get_function_or_404(db, function_id)
    if "code" in payload and payload["code"] != function.code:
        if db.scalar(select(SystemFunction).where(SystemFunction.code == payload["code"])):
            raise HTTPException(status_code=409, detail="Function code already exists")
    for field in ("name", "code", "module", "description", "is_active"):
        if field in payload:
            setattr(function, field, payload[field])
    function.updated_at = datetime.utcnow()
    db.add(function)
    db.commit()
    db.refresh(function)
    return function

def delete_system_function(db: Session, function_id: int) -> None:
    function = _get_function_or_404(db, function_id)
    db.delete(function)
    db.commit()

def _replace_group_permissions(
    db: Session,
    group: PermissionGroup,
    permissions: list[dict[str, Any]],
) -> None:
    from sqlalchemy import delete
    db.execute(delete(PermissionGroupFunction).where(PermissionGroupFunction.group_id == group.id))
    db.flush()

    for permission in permissions:
        _get_function_or_404(db, permission["function_id"])
        db.add(
            PermissionGroupFunction(
                group_id=group.id,
                function_id=permission["function_id"],
                can_view=permission.get("can_view", True),
                can_create=permission.get("can_create", False),
                can_update=permission.get("can_update", False),
                can_delete=permission.get("can_delete", False),
            )
        )
