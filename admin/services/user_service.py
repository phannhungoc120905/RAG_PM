from typing import Any
from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload
from auth.service import hash_password
from db.models import User
from admin.services.common import _get_user_or_404, _get_group_or_404, _get_department_or_404, _get_position_or_404

def list_users(
    db: Session,
    page: int,
    page_size: int,
    search: str | None,
    role: str | None = None,
) -> tuple[list[User], int]:
    statement: Select[tuple[User]] = select(User).options(
        selectinload(User.permission_group),
        selectinload(User.department),
        selectinload(User.position),
    )
    count_statement = select(func.count()).select_from(User)

    if search:
        from sqlalchemy import or_
        criteria = or_(
            User.username.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    
    if role:
        statement = statement.where(User.role == role)
        count_statement = count_statement.where(User.role == role)

    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all())
    return items, total

def create_user(db: Session, payload: dict[str, Any]) -> User:
    _assert_unique_user(db, payload["username"], payload.get("email"))
    _validate_user_relations(
        db,
        payload.get("permission_group_id"),
        payload.get("department_id"),
        payload.get("position_id"),
    )
    user = User(
        username=payload["username"],
        email=payload.get("email"),
        hashed_password=hash_password(payload["password"]),
        role=payload.get("role", "user"),
        permission_group_id=payload.get("permission_group_id"),
        department_id=payload.get("department_id"),
        position_id=payload.get("position_id"),
        is_active=payload.get("is_active", True),
        auth_source=payload.get("auth_source", "local"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user(db: Session, user_id: int, payload: dict[str, Any]) -> User:
    user = _get_user_or_404(db, user_id)
    username = payload.get("username")
    email = payload.get("email")

    if username and username != user.username:
        if db.scalar(select(User).where(User.username == username)):
            raise HTTPException(status_code=409, detail="Username already exists")
        user.username = username

    if "email" in payload:
        email = payload["email"]
        if email != user.email:
            if email and db.scalar(select(User).where(User.email == email, User.id != user.id)):
                raise HTTPException(status_code=409, detail="Email already exists")
            user.email = email

    _validate_user_relations(
        db,
        payload.get("permission_group_id", user.permission_group_id) if "permission_group_id" in payload else user.permission_group_id,
        payload.get("department_id", user.department_id) if "department_id" in payload else user.department_id,
        payload.get("position_id", user.position_id) if "position_id" in payload else user.position_id,
    )

    for field in ("role", "is_active", "permission_group_id", "department_id", "position_id"):
        if field in payload:
            setattr(user, field, payload[field])

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def toggle_user_active(db: Session, user_id: int) -> bool:
    user = _get_user_or_404(db, user_id)
    user.is_active = not user.is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.is_active

def reset_user_password(db: Session, user_id: int, new_password: str) -> None:
    user = _get_user_or_404(db, user_id)
    user.hashed_password = hash_password(new_password)
    db.add(user)
    db.commit()

def _assert_unique_user(db: Session, username: str, email: str | None) -> None:
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="Username already exists")
    if email and db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email already exists")

def _validate_user_relations(
    db: Session,
    permission_group_id: int | None,
    department_id: int | None,
    position_id: int | None,
) -> None:
    if permission_group_id is not None:
        _get_group_or_404(db, permission_group_id)
    if department_id is not None:
        _get_department_or_404(db, department_id)
    if position_id is not None:
        position = _get_position_or_404(db, position_id)
        if department_id is not None and position.department_id not in {None, department_id}:
            raise HTTPException(status_code=400, detail="Position does not belong to selected department")
