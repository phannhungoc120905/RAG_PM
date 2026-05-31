from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from db.database import get_db
from auth.dependencies import require_action
from db.models import User
from admin.service import (
    create_api_key,
    list_api_keys,
    update_api_key,
    delete_api_key,
    create_permission_group,
    list_permission_groups,
    update_permission_group,
    delete_permission_group,
    list_system_functions,
    create_system_function,
    update_system_function,
    delete_system_function
)
from admin.schemas import (
    APIKeyCreateRequest,
    APIKeyUpdateRequest,
    APIKeyItem,
    APIKeysResponse,
    APIKeyCreateResponse,
    PermissionGroupCreateRequest,
    PermissionGroupUpdateRequest,
    PermissionGroupItem,
    PermissionGroupsResponse,
    PermissionAssignmentResponse,
    SystemFunctionCreateRequest,
    SystemFunctionUpdateRequest,
    SystemFunctionItem,
    SystemFunctionsResponse,
    MessageResponse
)

router = APIRouter(tags=["Security & Permissions"])

# --- API Keys ---
@router.get("/api-keys", response_model=APIKeysResponse)
async def get_api_keys(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    current_user: User = Depends(require_action("admin.security.api_keys.list")),
    db: Session = Depends(get_db),
) -> APIKeysResponse:
    items, total = list_api_keys(db, page, page_size, search)
    return APIKeysResponse(
        items=[
            APIKeyItem(
                id=item.id,
                name=item.name,
                description=item.description,
                is_active=item.is_active,
                created_by=item.created_by,
                created_at=item.created_at,
                updated_at=item.updated_at,
                key_hash_preview=f"{item.key_hash[:8]}...",
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.post("/api-keys", response_model=APIKeyCreateResponse)
async def add_api_key(
    payload: APIKeyCreateRequest,
    current_user: User = Depends(require_action("admin.security.api_keys.create")),
    db: Session = Depends(get_db),
) -> APIKeyCreateResponse:
    item, plain_key = create_api_key(db, int(current_user.id), payload.model_dump())
    return APIKeyCreateResponse(
        id=item.id,
        name=item.name,
        plain_key=plain_key,
        created_at=item.created_at,
    )

@router.put("/api-keys/{api_key_id}", response_model=APIKeyItem)
async def edit_api_key(
    api_key_id: int,
    payload: APIKeyUpdateRequest,
    current_user: User = Depends(require_action("admin.security.api_keys.update")),
    db: Session = Depends(get_db),
) -> APIKeyItem:
    item = update_api_key(db, api_key_id, payload.model_dump(exclude_none=True))
    return APIKeyItem(
        id=item.id,
        name=item.name,
        description=item.description,
        is_active=item.is_active,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
        key_hash_preview=f"{item.key_hash[:8]}...",
    )

@router.delete("/api-keys/{api_key_id}", response_model=MessageResponse)
async def remove_api_key(
    api_key_id: int,
    current_user: User = Depends(require_action("admin.security.api_keys.delete")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_api_key(db, api_key_id)
    return MessageResponse(message="API Key deleted")

# --- Permission Groups ---
def _serialize_permission_group(item) -> PermissionGroupItem:
    return PermissionGroupItem(
        id=item.id,
        name=item.name,
        code=item.code,
        description=item.description,
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
        permissions=[
            PermissionAssignmentResponse(
                function_id=perm.function_id,
                function_name=perm.function.name,
                function_code=perm.function.code,
                can_view=perm.can_view,
                can_create=perm.can_create,
                can_update=perm.can_update,
                can_delete=perm.can_delete,
            )
            for perm in item.function_permissions
        ],
    )

@router.get("/permission-groups", response_model=PermissionGroupsResponse)
async def get_permission_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    current_user: User = Depends(require_action("admin.security.permission_groups.list")),
    db: Session = Depends(get_db),
) -> PermissionGroupsResponse:
    items, total = list_permission_groups(db, page, page_size, search)
    return PermissionGroupsResponse(
        items=[_serialize_permission_group(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.post("/permission-groups", response_model=PermissionGroupItem)
async def add_permission_group(
    payload: PermissionGroupCreateRequest,
    current_user: User = Depends(require_action("admin.security.permission_groups.create")),
    db: Session = Depends(get_db),
) -> PermissionGroupItem:
    item = create_permission_group(db, payload.model_dump())
    return _serialize_permission_group(item)

@router.put("/permission-groups/{group_id}", response_model=PermissionGroupItem)
async def edit_permission_group(
    group_id: int,
    payload: PermissionGroupUpdateRequest,
    current_user: User = Depends(require_action("admin.security.permission_groups.update")),
    db: Session = Depends(get_db),
) -> PermissionGroupItem:
    item = update_permission_group(db, group_id, payload.model_dump(exclude_none=True))
    return _serialize_permission_group(item)

@router.delete("/permission-groups/{group_id}", response_model=MessageResponse)
async def remove_permission_group(
    group_id: int,
    current_user: User = Depends(require_action("admin.security.permission_groups.delete")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_permission_group(db, group_id)
    return MessageResponse(message="Permission group deleted")

# --- System Functions ---
@router.get("/system-functions", response_model=SystemFunctionsResponse)
async def get_system_functions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    module: str | None = None,
    current_user: User = Depends(require_action("admin.security.system_functions.list")),
    db: Session = Depends(get_db),
) -> SystemFunctionsResponse:
    items, total = list_system_functions(db, page, page_size, module)
    return SystemFunctionsResponse(
        items=[
            SystemFunctionItem(
                id=item.id,
                name=item.name,
                code=item.code,
                module=item.module,
                description=item.description,
                is_active=item.is_active,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.post("/system-functions", response_model=SystemFunctionItem)
async def add_system_function(
    payload: SystemFunctionCreateRequest,
    current_user: User = Depends(require_action("admin.security.system_functions.create")),
    db: Session = Depends(get_db),
) -> SystemFunctionItem:
    item = create_system_function(db, payload.model_dump())
    return SystemFunctionItem(
        id=item.id,
        name=item.name,
        code=item.code,
        module=item.module,
        description=item.description,
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

@router.put("/system-functions/{func_id}", response_model=SystemFunctionItem)
async def edit_system_function(
    func_id: int,
    payload: SystemFunctionUpdateRequest,
    current_user: User = Depends(require_action("admin.security.system_functions.update")),
    db: Session = Depends(get_db),
) -> SystemFunctionItem:
    item = update_system_function(db, func_id, payload.model_dump(exclude_none=True))
    return SystemFunctionItem(
        id=item.id,
        name=item.name,
        code=item.code,
        module=item.module,
        description=item.description,
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

@router.delete("/system-functions/{func_id}", response_model=MessageResponse)
async def remove_system_function(
    func_id: int,
    current_user: User = Depends(require_action("admin.security.system_functions.delete")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_system_function(db, func_id)
    return MessageResponse(message="System function deleted")
