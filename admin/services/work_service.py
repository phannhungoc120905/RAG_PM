from datetime import datetime
from typing import Any
from fastapi import HTTPException
from sqlalchemy import Select, func, select, or_
from sqlalchemy.orm import Session, selectinload
from db.models import WorkAssignmentDocument, WorkItem, NoticeDocument, User
from admin.services.common import (
    _get_work_document_or_404,
    _get_work_item_or_404,
    _get_notice_document_or_404,
    _get_issuing_unit_or_404,
    _get_department_or_404,
    _get_user_or_404,
    _get_position_or_404
)

def list_work_documents(
    db: Session,
    page: int,
    page_size: int,
    search: str | None,
    status_value: str | None,
    current_user: User | None = None,
    issuing_unit_id: int | None = None,
    department_id: int | None = None,
    assigned_department_id: int | None = None,
) -> tuple[list[WorkAssignmentDocument], int]:
    statement: Select[tuple[WorkAssignmentDocument]] = select(WorkAssignmentDocument).options(
        selectinload(WorkAssignmentDocument.issuing_unit),
        selectinload(WorkAssignmentDocument.department),
        selectinload(WorkAssignmentDocument.assigned_department),
        selectinload(WorkAssignmentDocument.assigned_by_user),
        selectinload(WorkAssignmentDocument.work_items),
    )
    count_statement = select(func.count()).select_from(WorkAssignmentDocument)
    if search:
        criteria = or_(
            WorkAssignmentDocument.document_code.ilike(f"%{search}%"),
            WorkAssignmentDocument.title.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    if status_value:
        statement = statement.where(WorkAssignmentDocument.status == status_value)
        count_statement = count_statement.where(WorkAssignmentDocument.status == status_value)
    if issuing_unit_id is not None:
        statement = statement.where(WorkAssignmentDocument.issuing_unit_id == issuing_unit_id)
        count_statement = count_statement.where(WorkAssignmentDocument.issuing_unit_id == issuing_unit_id)
    if department_id is not None:
        statement = statement.where(WorkAssignmentDocument.department_id == department_id)
        count_statement = count_statement.where(WorkAssignmentDocument.department_id == department_id)
    if assigned_department_id is not None:
        statement = statement.where(WorkAssignmentDocument.assigned_department_id == assigned_department_id)
        count_statement = count_statement.where(WorkAssignmentDocument.assigned_department_id == assigned_department_id)

    if current_user:
        group_code = _get_group_code(current_user)
        if group_code == "DEPARTMENT_LEADER":
            if current_user.department_id is None:
                raise HTTPException(status_code=403, detail="Department scope is required")
            statement = statement.where(
                or_(
                    WorkAssignmentDocument.department_id == current_user.department_id,
                    WorkAssignmentDocument.assigned_department_id == current_user.department_id,
                )
            )
            count_statement = count_statement.where(
                or_(
                    WorkAssignmentDocument.department_id == current_user.department_id,
                    WorkAssignmentDocument.assigned_department_id == current_user.department_id,
                )
            )
    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(WorkAssignmentDocument.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all())
    return items, total

def create_work_document(
    db: Session,
    payload: dict[str, Any],
    current_user: User | None = None,
) -> WorkAssignmentDocument:
    if db.scalar(select(WorkAssignmentDocument).where(WorkAssignmentDocument.document_code == payload["document_code"])):
        raise HTTPException(status_code=409, detail="Work document code already exists")
    if current_user:
        _assert_can_manage_work_documents(db, current_user, payload)
        payload.setdefault("assigned_by_user_id", current_user.id)
    _validate_work_document_relations(db, payload)
    item = WorkAssignmentDocument(**payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def update_work_document(
    db: Session,
    document_id: int,
    payload: dict[str, Any],
    current_user: User | None = None,
) -> WorkAssignmentDocument:
    item = _get_work_document_or_404(db, document_id)
    if "document_code" in payload and payload["document_code"] != item.document_code:
        if db.scalar(select(WorkAssignmentDocument).where(WorkAssignmentDocument.document_code == payload["document_code"])):
            raise HTTPException(status_code=409, detail="Work document code already exists")
    if current_user:
        _assert_can_manage_work_documents(db, current_user, payload, document_id=document_id)
    _validate_work_document_relations(db, payload)
    for field, value in payload.items():
        setattr(item, field, value)
    item.updated_at = datetime.utcnow()
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def delete_work_document(
    db: Session,
    document_id: int,
    current_user: User | None = None,
) -> None:
    if current_user:
        _assert_can_manage_work_documents(db, current_user, document_id=document_id)
    item = _get_work_document_or_404(db, document_id)
    db.delete(item)
    db.commit()

def list_work_items(
    db: Session,
    page: int,
    page_size: int,
    search: str | None,
    status_value: str | None,
    work_document_id: int | None,
    assignee_user_id: int | None,
    department_id: int | None,
    current_user: User | None = None,
) -> tuple[list[WorkItem], int]:
    statement: Select[tuple[WorkItem]] = select(WorkItem).options(
        selectinload(WorkItem.work_document),
        selectinload(WorkItem.assignee),
        selectinload(WorkItem.department),
        selectinload(WorkItem.position),
    )
    count_statement = select(func.count()).select_from(WorkItem)
    if search:
        criteria = or_(
            WorkItem.title.ilike(f"%{search}%"),
            WorkItem.description.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    if status_value:
        statement = statement.where(WorkItem.status == status_value)
        count_statement = count_statement.where(WorkItem.status == status_value)
    if work_document_id is not None:
        statement = statement.where(WorkItem.work_document_id == work_document_id)
        count_statement = count_statement.where(WorkItem.work_document_id == work_document_id)
    if assignee_user_id is not None:
        statement = statement.where(WorkItem.assignee_user_id == assignee_user_id)
        count_statement = count_statement.where(WorkItem.assignee_user_id == assignee_user_id)
    if department_id is not None:
        statement = statement.where(WorkItem.department_id == department_id)
        count_statement = count_statement.where(WorkItem.department_id == department_id)

    if current_user:
        group_code = _get_group_code(current_user)
        if group_code == "DEPARTMENT_LEADER":
            if current_user.department_id is None:
                raise HTTPException(status_code=403, detail="Department scope is required")
            statement = statement.where(WorkItem.department_id == current_user.department_id)
            count_statement = count_statement.where(WorkItem.department_id == current_user.department_id)
        elif group_code == "STAFF":
            statement = statement.where(WorkItem.assignee_user_id == current_user.id)
            count_statement = count_statement.where(WorkItem.assignee_user_id == current_user.id)
    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(WorkItem.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all())
    return items, total

def create_work_item(
    db: Session,
    payload: dict[str, Any],
    current_user: User | None = None,
) -> WorkItem:
    if current_user:
        _assert_can_manage_work_items(current_user, payload)
    _validate_work_item_relations(db, payload)
    item = WorkItem(**payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def update_work_item(
    db: Session,
    item_id: int,
    payload: dict[str, Any],
    current_user: User | None = None,
) -> WorkItem:
    item = _get_work_item_or_404(db, item_id)
    if current_user:
        _assert_can_manage_work_items(current_user, payload, item=item)
    _validate_work_item_relations(db, payload)
    for field, value in payload.items():
        setattr(item, field, value)
    item.updated_at = datetime.utcnow()
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def delete_work_item(
    db: Session,
    item_id: int,
    current_user: User | None = None,
) -> None:
    item = _get_work_item_or_404(db, item_id)
    if current_user:
        _assert_can_manage_work_items(current_user, {}, item=item)
    db.delete(item)
    db.commit()

def list_notice_documents(
    db: Session,
    page: int,
    page_size: int,
    search: str | None,
    status_value: str | None = None,
    issuing_unit_id: int | None = None,
    department_id: int | None = None,
) -> tuple[list[NoticeDocument], int]:
    statement: Select[tuple[NoticeDocument]] = select(NoticeDocument).options(
        selectinload(NoticeDocument.issuing_unit),
        selectinload(NoticeDocument.department),
        selectinload(NoticeDocument.posted_by_user),
    )
    count_statement = select(func.count()).select_from(NoticeDocument)
    if search:
        criteria = or_(
            NoticeDocument.notice_code.ilike(f"%{search}%"),
            NoticeDocument.title.ilike(f"%{search}%"),
        )
        statement = statement.where(criteria)
        count_statement = count_statement.where(criteria)
    if status_value:
        statement = statement.where(NoticeDocument.status == status_value)
        count_statement = count_statement.where(NoticeDocument.status == status_value)
    if issuing_unit_id is not None:
        statement = statement.where(NoticeDocument.issuing_unit_id == issuing_unit_id)
        count_statement = count_statement.where(NoticeDocument.issuing_unit_id == issuing_unit_id)
    if department_id is not None:
        statement = statement.where(NoticeDocument.department_id == department_id)
        count_statement = count_statement.where(NoticeDocument.department_id == department_id)
    total = db.scalar(count_statement) or 0
    items = list(db.scalars(
        statement.order_by(NoticeDocument.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all())
    return items, total

def create_notice_document(
    db: Session,
    actor_user_id: int,
    payload: dict[str, Any],
    current_user: User | None = None,
) -> NoticeDocument:
    if db.scalar(select(NoticeDocument).where(NoticeDocument.notice_code == payload["notice_code"])):
        raise HTTPException(status_code=409, detail="Notice code already exists")
    payload["posted_by_user_id"] = actor_user_id
    _validate_notice_relations(db, payload)
    item = NoticeDocument(**payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def update_notice_document(db: Session, notice_id: int, payload: dict[str, Any]) -> NoticeDocument:
    item = _get_notice_document_or_404(db, notice_id)
    if "notice_code" in payload and payload["notice_code"] != item.notice_code:
        if db.scalar(select(NoticeDocument).where(NoticeDocument.notice_code == payload["notice_code"])):
            raise HTTPException(status_code=409, detail="Notice code already exists")
    _validate_notice_relations(db, payload)
    for field, value in payload.items():
        setattr(item, field, value)
    item.updated_at = datetime.utcnow()
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def delete_notice_document(
    db: Session,
    notice_id: int,
    current_user: User | None = None,
) -> None:
    item = _get_notice_document_or_404(db, notice_id)
    db.delete(item)
    db.commit()

def _validate_work_document_relations(db: Session, payload: dict[str, Any]) -> None:
    if payload.get("issuing_unit_id") is not None:
        _get_issuing_unit_or_404(db, payload["issuing_unit_id"])
    if payload.get("department_id") is not None:
        _get_department_or_404(db, payload["department_id"])
    if payload.get("assigned_department_id") is not None:
        _get_department_or_404(db, payload["assigned_department_id"])
    if payload.get("assigned_by_user_id") is not None:
        _get_user_or_404(db, payload["assigned_by_user_id"])

def _validate_work_item_relations(db: Session, payload: dict[str, Any]) -> None:
    if payload.get("work_document_id") is not None:
        _get_work_document_or_404(db, payload["work_document_id"])
    if payload.get("assignee_user_id") is not None:
        _get_user_or_404(db, payload["assignee_user_id"])
    if payload.get("department_id") is not None:
        _get_department_or_404(db, payload["department_id"])
    if payload.get("position_id") is not None:
        _get_position_or_404(db, payload["position_id"])

def _validate_notice_relations(db: Session, payload: dict[str, Any]) -> None:
    if payload.get("issuing_unit_id") is not None:
        _get_issuing_unit_or_404(db, payload["issuing_unit_id"])
    if payload.get("department_id") is not None:
        _get_department_or_404(db, payload["department_id"])
    if payload.get("posted_by_user_id") is not None:
        _get_user_or_404(db, payload["posted_by_user_id"])


def _get_group_code(user: User) -> str | None:
    if user.permission_group:
        return user.permission_group.code
    return None


def _assert_can_manage_work_documents(
    db: Session,
    current_user: User,
    payload: dict[str, Any] | None = None,
    document_id: int | None = None,
) -> None:
    payload = payload or {}
    group_code = _get_group_code(current_user)
    if group_code == "AGENCY_LEADER":
        return
    if group_code != "DEPARTMENT_LEADER":
        raise HTTPException(status_code=403, detail="Permission denied")

    if current_user.department_id is None:
        raise HTTPException(status_code=403, detail="Department scope is required")

    department_id = payload.get("department_id")
    assigned_department_id = payload.get("assigned_department_id")
    if department_id and department_id != current_user.department_id:
        raise HTTPException(status_code=403, detail="Department scope violation")
    if assigned_department_id and assigned_department_id != current_user.department_id:
        raise HTTPException(status_code=403, detail="Department scope violation")

    if document_id is not None:
        document = _get_work_document_or_404(db, document_id)
        if document.department_id not in {None, current_user.department_id} and document.assigned_department_id not in {None, current_user.department_id}:
            raise HTTPException(status_code=403, detail="Department scope violation")


def _assert_can_manage_work_items(
    current_user: User,
    payload: dict[str, Any],
    item: WorkItem | None = None,
) -> None:
    group_code = _get_group_code(current_user)
    if group_code == "AGENCY_LEADER":
        return
    if group_code != "DEPARTMENT_LEADER":
        raise HTTPException(status_code=403, detail="Permission denied")

    if current_user.department_id is None:
        raise HTTPException(status_code=403, detail="Department scope is required")

    department_id = payload.get("department_id") or (item.department_id if item else None)
    if department_id and department_id != current_user.department_id:
        raise HTTPException(status_code=403, detail="Department scope violation")
