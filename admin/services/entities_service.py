from datetime import datetime
from typing import Any
from fastapi import HTTPException
from sqlalchemy import Select, func, select, or_
from sqlalchemy.orm import Session, selectinload
from db.models import IssuingUnit, Department, Position
from admin.services.common import _get_issuing_unit_or_404, _get_department_or_404, _get_position_or_404

def list_issuing_units(
    db: Session,
    page: int,
    page_size: int,
    search: str | None,
    is_active: bool | None,
) -> tuple[list[IssuingUnit], int]:
    statement: Select[tuple[IssuingUnit]] = select(IssuingUnit).options(selectinload(IssuingUnit.parent))
    count_statement = select(func.count()).select_from(IssuingUnit)
    if search:
        criteria = or_(
            IssuingUnit.code.ilike(f"%{search}%"),
            IssuingUnit.name.ilike(f"%{search}%"),
            IssuingUnit.short_name.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    if is_active is not None:
        statement = statement.where(IssuingUnit.is_active == is_active)
        count_statement = count_statement.where(IssuingUnit.is_active == is_active)
    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(IssuingUnit.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all())
    return items, total

def create_issuing_unit(db: Session, payload: dict[str, Any]) -> IssuingUnit:
    if db.scalar(select(IssuingUnit).where(IssuingUnit.code == payload["code"])):
        raise HTTPException(status_code=409, detail="Issuing unit code already exists")
    if payload.get("parent_id") is not None:
        _get_issuing_unit_or_404(db, payload["parent_id"])
    item = IssuingUnit(**payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def update_issuing_unit(db: Session, unit_id: int, payload: dict[str, Any]) -> IssuingUnit:
    item = _get_issuing_unit_or_404(db, unit_id)
    if "code" in payload and payload["code"] != item.code:
        if db.scalar(select(IssuingUnit).where(IssuingUnit.code == payload["code"])):
            raise HTTPException(status_code=409, detail="Issuing unit code already exists")
    if "parent_id" in payload:
        if payload["parent_id"] == unit_id:
            raise HTTPException(status_code=400, detail="Parent cannot be self")
        if payload["parent_id"] is not None:
            _get_issuing_unit_or_404(db, payload["parent_id"])
    for field, value in payload.items():
        setattr(item, field, value)
    item.updated_at = datetime.utcnow()
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def delete_issuing_unit(db: Session, unit_id: int) -> None:
    item = _get_issuing_unit_or_404(db, unit_id)
    if item.children or item.departments or item.work_assignment_documents or item.notice_documents:
        raise HTTPException(status_code=400, detail="Issuing unit is in use")
    db.delete(item)
    db.commit()

def list_departments(
    db: Session,
    page: int,
    page_size: int,
    search: str | None,
    issuing_unit_id: int | None,
    is_active: bool | None,
) -> tuple[list[Department], int]:
    statement: Select[tuple[Department]] = select(Department).options(
        selectinload(Department.issuing_unit),
        selectinload(Department.parent),
    )
    count_statement = select(func.count()).select_from(Department)
    if search:
        criteria = or_(
            Department.code.ilike(f"%{search}%"),
            Department.name.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    if issuing_unit_id is not None:
        statement = statement.where(Department.issuing_unit_id == issuing_unit_id)
        count_statement = count_statement.where(Department.issuing_unit_id == issuing_unit_id)
    if is_active is not None:
        statement = statement.where(Department.is_active == is_active)
        count_statement = count_statement.where(Department.is_active == is_active)
    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(Department.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all())
    return items, total

def create_department(db: Session, payload: dict[str, Any]) -> Department:
    if db.scalar(select(Department).where(Department.code == payload["code"])):
        raise HTTPException(status_code=409, detail="Department code already exists")
    if payload.get("issuing_unit_id") is not None:
        _get_issuing_unit_or_404(db, payload["issuing_unit_id"])
    if payload.get("parent_id") is not None:
        _get_department_or_404(db, payload["parent_id"])
    item = Department(**payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def update_department(db: Session, department_id: int, payload: dict[str, Any]) -> Department:
    item = _get_department_or_404(db, department_id)
    if "code" in payload and payload["code"] != item.code:
        if db.scalar(select(Department).where(Department.code == payload["code"])):
            raise HTTPException(status_code=409, detail="Department code already exists")
    if "issuing_unit_id" in payload and payload["issuing_unit_id"] is not None:
        _get_issuing_unit_or_404(db, payload["issuing_unit_id"])
    if "parent_id" in payload:
        if payload["parent_id"] == department_id:
            raise HTTPException(status_code=400, detail="Parent cannot be self")
        if payload["parent_id"] is not None:
            _get_department_or_404(db, payload["parent_id"])
    for field, value in payload.items():
        setattr(item, field, value)
    item.updated_at = datetime.utcnow()
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def delete_department(db: Session, department_id: int) -> None:
    item = _get_department_or_404(db, department_id)
    if item.children or item.positions or item.users or item.work_items or item.work_assignment_documents or item.assigned_work_documents or item.notice_documents:
        raise HTTPException(status_code=400, detail="Department is in use")
    db.delete(item)
    db.commit()

def list_positions(
    db: Session,
    page: int,
    page_size: int,
    search: str | None,
    department_id: int | None,
    is_active: bool | None,
) -> tuple[list[Position], int]:
    statement: Select[tuple[Position]] = select(Position).options(selectinload(Position.department))
    count_statement = select(func.count()).select_from(Position)
    if search:
        criteria = or_(
            Position.code.ilike(f"%{search}%"),
            Position.name.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    if department_id is not None:
        statement = statement.where(Position.department_id == department_id)
        count_statement = count_statement.where(Position.department_id == department_id)
    if is_active is not None:
        statement = statement.where(Position.is_active == is_active)
        count_statement = count_statement.where(Position.is_active == is_active)
    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(Position.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all())
    return items, total

def create_position(db: Session, payload: dict[str, Any]) -> Position:
    if db.scalar(select(Position).where(Position.code == payload["code"])):
        raise HTTPException(status_code=409, detail="Position code already exists")
    if payload.get("department_id") is not None:
        _get_department_or_404(db, payload["department_id"])
    item = Position(**payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def update_position(db: Session, position_id: int, payload: dict[str, Any]) -> Position:
    item = _get_position_or_404(db, position_id)
    if "code" in payload and payload["code"] != item.code:
        if db.scalar(select(Position).where(Position.code == payload["code"])):
            raise HTTPException(status_code=409, detail="Position code already exists")
    if "department_id" in payload and payload["department_id"] is not None:
        _get_department_or_404(db, payload["department_id"])
    for field, value in payload.items():
        setattr(item, field, value)
    item.updated_at = datetime.utcnow()
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def delete_position(db: Session, position_id: int) -> None:
    item = _get_position_or_404(db, position_id)
    if item.users or item.work_items:
        raise HTTPException(status_code=400, detail="Position is in use")
    db.delete(item)
    db.commit()
