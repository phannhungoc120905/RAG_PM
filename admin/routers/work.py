from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from db.database import get_db
from auth.dependencies import require_admin
from admin.service import (
    list_work_documents,
    create_work_document,
    update_work_document,
    delete_work_document,
    list_work_items,
    create_work_item,
    update_work_item,
    delete_work_item,
    list_notice_documents,
    create_notice_document,
    delete_notice_document
)
from admin.schemas import (
    WorkDocumentsResponse,
    WorkDocumentItem,
    WorkDocumentCreateRequest,
    WorkDocumentUpdateRequest,
    WorkItemsResponse,
    WorkItemEntry,
    WorkItemCreateRequest,
    WorkItemUpdateRequest,
    NoticeDocumentsResponse,
    NoticeDocumentItem,
    NoticeDocumentCreateRequest,
    MessageResponse
)

router = APIRouter(tags=["Work & Document Management"])

# --- Work Documents ---
def _serialize_work_document(item) -> WorkDocumentItem:
    return WorkDocumentItem(
        id=item.id,
        document_code=item.document_code,
        title=item.title,
        content_summary=item.content_summary,
        issuing_unit_id=item.issuing_unit_id,
        issuing_unit_name=item.issuing_unit.name if item.issuing_unit else None,
        department_id=item.department_id,
        department_name=item.department.name if item.department else None,
        assigned_by_user_id=item.assigned_by_user_id,
        assigned_by_username=item.assigned_by_user.username if item.assigned_by_user else None,
        assigned_department_id=item.assigned_department_id,
        assigned_department_name=item.assigned_department.name if item.assigned_department else None,
        due_date=item.due_date,
        status=item.status,
        work_item_count=len(item.work_items or []),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

@router.get("/work-documents", response_model=WorkDocumentsResponse)
async def get_work_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    status: str | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkDocumentsResponse:
    del admin_user
    items, total = list_work_documents(db, page, page_size, search, status)
    return WorkDocumentsResponse(
        items=[_serialize_work_document(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.post("/work-documents", response_model=WorkDocumentItem)
async def add_work_document(
    payload: WorkDocumentCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkDocumentItem:
    del admin_user
    item = create_work_document(db, payload.model_dump())
    return _serialize_work_document(item)

@router.put("/work-documents/{doc_id}", response_model=WorkDocumentItem)
async def edit_work_document(
    doc_id: int,
    payload: WorkDocumentUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkDocumentItem:
    del admin_user
    item = update_work_document(db, doc_id, payload.model_dump(exclude_none=True))
    return _serialize_work_document(item)

@router.delete("/work-documents/{doc_id}", response_model=MessageResponse)
async def remove_work_document(
    doc_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_work_document(db, doc_id)
    return MessageResponse(message="Work document deleted")

# --- Work Items ---
def _serialize_work_item(item) -> WorkItemEntry:
    return WorkItemEntry(
        id=item.id,
        work_document_id=item.work_document_id,
        work_document_code=item.work_document.document_code if item.work_document else None,
        title=item.title,
        description=item.description,
        assignee_user_id=item.assignee_user_id,
        assignee_username=item.assignee.username if item.assignee else None,
        department_id=item.department_id,
        department_name=item.department.name if item.department else None,
        position_id=item.position_id,
        position_name=item.position.name if item.position else None,
        priority=item.priority,
        status=item.status,
        due_date=item.due_date,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

@router.get("/work-items", response_model=WorkItemsResponse)
async def get_work_items(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    status: str | None = None,
    doc_id: int | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkItemsResponse:
    del admin_user
    items, total = list_work_items(db, page, page_size, search, status, doc_id)
    return WorkItemsResponse(
        items=[_serialize_work_item(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.post("/work-items", response_model=WorkItemEntry)
async def add_work_item(
    payload: WorkItemCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkItemEntry:
    del admin_user
    item = create_work_item(db, payload.model_dump())
    return _serialize_work_item(item)

@router.put("/work-items/{item_id}", response_model=WorkItemEntry)
async def edit_work_item(
    item_id: int,
    payload: WorkItemUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkItemEntry:
    del admin_user
    item = update_work_item(db, item_id, payload.model_dump(exclude_none=True))
    return _serialize_work_item(item)

@router.delete("/work-items/{item_id}", response_model=MessageResponse)
async def remove_work_item(
    item_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_work_item(db, item_id)
    return MessageResponse(message="Work item deleted")

# --- Notice Documents ---
@router.get("/notice-documents", response_model=NoticeDocumentsResponse)
async def get_notice_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> NoticeDocumentsResponse:
    del admin_user
    items, total = list_notice_documents(db, page, page_size, search)
    return NoticeDocumentsResponse(
        items=[
            NoticeDocumentItem(
                id=item.id,
                notice_code=item.notice_code,
                title=item.title,
                content=item.content,
                issuing_unit_id=item.issuing_unit_id,
                issuing_unit_name=item.issuing_unit.name if item.issuing_unit else None,
                department_id=item.department_id,
                department_name=item.department.name if item.department else None,
                posted_by_user_id=item.posted_by_user_id,
                posted_by_username=item.posted_by_user.username if item.posted_by_user else None,
                effective_date=item.effective_date,
                status=item.status,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.post("/notice-documents", response_model=NoticeDocumentItem)
async def add_notice_document(
    payload: NoticeDocumentCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> NoticeDocumentItem:
    del admin_user
    item = create_notice_document(db, int(admin_user["sub"]), payload.model_dump())
    return NoticeDocumentItem(
        id=item.id,
        notice_code=item.notice_code,
        title=item.title,
        content=item.content,
        issuing_unit_id=item.issuing_unit_id,
        issuing_unit_name=item.issuing_unit.name if item.issuing_unit else None,
        department_id=item.department_id,
        department_name=item.department.name if item.department else None,
        posted_by_user_id=item.posted_by_user_id,
        posted_by_username=item.posted_by_user.username if item.posted_by_user else None,
        effective_date=item.effective_date,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

@router.delete("/notice-documents/{doc_id}", response_model=MessageResponse)
async def remove_notice_document(
    doc_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_notice_document(db, doc_id)
    return MessageResponse(message="Notice document deleted")
