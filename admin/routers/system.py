from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from db.database import get_db
from auth.dependencies import require_admin
from admin.service import (
    list_system_configs,
    create_system_config,
    update_system_config,
    delete_system_config,
    get_system_status,
    get_safe_config,
    update_runtime_config
)
from admin.schemas import (
    SystemConfigsResponse,
    SystemConfigItem,
    SystemConfigCreateRequest,
    SystemConfigUpdateRequest,
    SystemStatusResponse,
    AdminConfigResponse,
    AdminConfigUpdateRequest,
    MessageResponse
)

router = APIRouter(tags=["System Administration"])

@router.get("/configs", response_model=SystemConfigsResponse)
async def get_system_configs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    category: str | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemConfigsResponse:
    del admin_user
    items, total = list_system_configs(db, page, page_size, search, category)
    return SystemConfigsResponse(
        items=[
            SystemConfigItem(
                id=item.id,
                config_key=item.config_key,
                config_value=item.config_value,
                category=item.category,
                data_type=item.data_type,
                description=item.description,
                is_active=item.is_active,
                updated_by=item.updated_by,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.post("/configs", response_model=SystemConfigItem)
async def create_config(
    payload: SystemConfigCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemConfigItem:
    item = create_system_config(db, int(admin_user["sub"]), payload.model_dump())
    return SystemConfigItem(
        id=item.id,
        config_key=item.config_key,
        config_value=item.config_value,
        category=item.category,
        data_type=item.data_type,
        description=item.description,
        is_active=item.is_active,
        updated_by=item.updated_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

@router.put("/configs/{config_id}", response_model=SystemConfigItem)
async def edit_config(
    config_id: int,
    payload: SystemConfigUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemConfigItem:
    item = update_system_config(
        db,
        config_id,
        int(admin_user["sub"]),
        payload.model_dump(exclude_none=True),
    )
    return SystemConfigItem(
        id=item.id,
        config_key=item.config_key,
        config_value=item.config_value,
        category=item.category,
        data_type=item.data_type,
        description=item.description,
        is_active=item.is_active,
        updated_by=item.updated_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

@router.delete("/configs/{config_id}", response_model=MessageResponse)
async def remove_config(
    config_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_system_config(db, config_id)
    return MessageResponse(message="Config deleted")

@router.get("/status", response_model=SystemStatusResponse)
async def get_status(
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemStatusResponse:
    del admin_user
    return get_system_status(db)

@router.get("/app-config", response_model=AdminConfigResponse)
async def get_app_config(
    admin_user: dict = Depends(require_admin),
) -> AdminConfigResponse:
    del admin_user
    config = get_safe_config()
    return AdminConfigResponse(**config)

@router.put("/app-config", response_model=AdminConfigResponse)
async def update_app_config(
    payload: AdminConfigUpdateRequest,
    admin_user: dict = Depends(require_admin),
) -> AdminConfigResponse:
    del admin_user
    config = update_runtime_config(payload.model_dump(exclude_none=True))
    return AdminConfigResponse(**config)
