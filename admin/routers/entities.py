from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from db.database import get_db
from auth.dependencies import require_admin
from admin.service import (
    list_issuing_units,
    create_issuing_unit,
    update_issuing_unit,
    delete_issuing_unit,
    list_departments,
    create_department,
    update_department,
    delete_department,
    list_positions,
    create_position,
    update_position,
    delete_position
)
from admin.schemas import (
    IssuingUnitsResponse,
    IssuingUnitItem,
    IssuingUnitCreateRequest,
    IssuingUnitUpdateRequest,
    DepartmentsResponse,
    DepartmentItem,
    DepartmentCreateRequest,
    DepartmentUpdateRequest,
    PositionsResponse,
    PositionItem,
    PositionCreateRequest,
    PositionUpdateRequest,
    MessageResponse
)

router = APIRouter(tags=["Administrative Entities"])

# --- Issuing Units ---
def _serialize_issuing_unit(item) -> IssuingUnitItem:
    return IssuingUnitItem(
        id=item.id,
        code=item.code,
        name=item.name,
        short_name=item.short_name,
        parent_id=item.parent_id,
        parent_name=item.parent.name if item.parent else None,
        address=item.address,
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

@router.get("/issuing-units", response_model=IssuingUnitsResponse)
async def get_issuing_units(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IssuingUnitsResponse:
    del admin_user
    items, total = list_issuing_units(db, page, page_size, search)
    return IssuingUnitsResponse(
        items=[_serialize_issuing_unit(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.post("/issuing-units", response_model=IssuingUnitItem)
async def add_issuing_unit(
    payload: IssuingUnitCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IssuingUnitItem:
    del admin_user
    item = create_issuing_unit(db, payload.model_dump())
    return _serialize_issuing_unit(item)

@router.put("/issuing-units/{unit_id}", response_model=IssuingUnitItem)
async def edit_issuing_unit(
    unit_id: int,
    payload: IssuingUnitUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IssuingUnitItem:
    del admin_user
    item = update_issuing_unit(db, unit_id, payload.model_dump(exclude_none=True))
    return _serialize_issuing_unit(item)

@router.delete("/issuing-units/{unit_id}", response_model=MessageResponse)
async def remove_issuing_unit(
    unit_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_issuing_unit(db, unit_id)
    return MessageResponse(message="Issuing unit deleted")

# --- Departments ---
def _serialize_department(item) -> DepartmentItem:
    return DepartmentItem(
        id=item.id,
        code=item.code,
        name=item.name,
        issuing_unit_id=item.issuing_unit_id,
        issuing_unit_name=item.issuing_unit.name if item.issuing_unit else None,
        parent_id=item.parent_id,
        parent_name=item.parent.name if item.parent else None,
        description=item.description,
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

@router.get("/departments", response_model=DepartmentsResponse)
async def get_departments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    unit_id: int | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DepartmentsResponse:
    del admin_user
    items, total = list_departments(db, page, page_size, search, unit_id)
    return DepartmentsResponse(
        items=[_serialize_department(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.post("/departments", response_model=DepartmentItem)
async def add_department(
    payload: DepartmentCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DepartmentItem:
    del admin_user
    item = create_department(db, payload.model_dump())
    return _serialize_department(item)

@router.put("/departments/{dept_id}", response_model=DepartmentItem)
async def edit_department(
    dept_id: int,
    payload: DepartmentUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DepartmentItem:
    del admin_user
    item = update_department(db, dept_id, payload.model_dump(exclude_none=True))
    return _serialize_department(item)

@router.delete("/departments/{dept_id}", response_model=MessageResponse)
async def remove_department(
    dept_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_department(db, dept_id)
    return MessageResponse(message="Department deleted")

# --- Positions ---
def _serialize_position(item) -> PositionItem:
    return PositionItem(
        id=item.id,
        code=item.code,
        name=item.name,
        department_id=item.department_id,
        department_name=item.department.name if item.department else None,
        description=item.description,
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

@router.get("/positions", response_model=PositionsResponse)
async def get_positions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    dept_id: int | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PositionsResponse:
    del admin_user
    items, total = list_positions(db, page, page_size, search, dept_id)
    return PositionsResponse(
        items=[_serialize_position(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.post("/positions", response_model=PositionItem)
async def add_position(
    payload: PositionCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PositionItem:
    del admin_user
    item = create_position(db, payload.model_dump())
    return _serialize_position(item)

@router.put("/positions/{pos_id}", response_model=PositionItem)
async def edit_position(
    pos_id: int,
    payload: PositionUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PositionItem:
    del admin_user
    item = update_position(db, pos_id, payload.model_dump(exclude_none=True))
    return _serialize_position(item)

@router.delete("/positions/{pos_id}", response_model=MessageResponse)
async def remove_position(
    pos_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_position(db, pos_id)
    return MessageResponse(message="Position deleted")
