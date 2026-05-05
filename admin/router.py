from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from admin.service import (
    create_api_key,
    create_backup,
    create_permission_group,
    create_system_config,
    create_system_function,
    create_user,
    delete_api_key,
    delete_permission_group,
    delete_system_config,
    delete_system_function,
    export_logs_to_excel,
    get_safe_config,
    get_system_status,
    list_api_keys,
    list_backups,
    list_logs,
    list_permission_groups,
    list_system_configs,
    list_system_functions,
    list_users,
    reset_user_password,
    restore_backup,
    toggle_user_active,
    update_api_key,
    update_permission_group,
    update_runtime_config,
    update_system_config,
    update_system_function,
    update_user,
)
from auth.dependencies import require_admin
from db.database import get_db


router = APIRouter()


# =============== HTML PAGES (NO AUTH REQUIRED) ===============
def read_html_file(filename: str, fallback: str) -> str:
    path = Path(filename)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


@router.get("/users-ui", response_class=HTMLResponse)
async def admin_users_page() -> str:
    return read_html_file("users_management.html", "<h1>Users Management</h1>")


@router.get("/system-config-ui", response_class=HTMLResponse)
async def admin_system_config_page() -> str:
    return read_html_file("system_config_ui.html", "<h1>System Config</h1>")


# =============== API ROUTES (WITH AUTH) ===============



class PermissionAssignmentRequest(BaseModel):
    function_id: int
    can_view: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False


class PermissionAssignmentResponse(PermissionAssignmentRequest):
    function_name: str
    function_code: str


class PermissionGroupCreateRequest(BaseModel):
    name: str
    code: str
    description: str | None = None
    is_active: bool = True
    permissions: list[PermissionAssignmentRequest] = Field(default_factory=list)


class PermissionGroupUpdateRequest(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    is_active: bool | None = None
    permissions: list[PermissionAssignmentRequest] | None = None


class PermissionGroupItem(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None
    permissions: list[PermissionAssignmentResponse]


class PermissionGroupsResponse(BaseModel):
    items: list[PermissionGroupItem]
    total: int
    page: int
    page_size: int


class SystemFunctionCreateRequest(BaseModel):
    name: str
    code: str
    module: str | None = None
    description: str | None = None
    is_active: bool = True


class SystemFunctionUpdateRequest(BaseModel):
    name: str | None = None
    code: str | None = None
    module: str | None = None
    description: str | None = None
    is_active: bool | None = None


class SystemFunctionItem(BaseModel):
    id: int
    name: str
    code: str
    module: str | None
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None


class SystemFunctionsResponse(BaseModel):
    items: list[SystemFunctionItem]
    total: int
    page: int
    page_size: int


class SystemConfigCreateRequest(BaseModel):
    config_key: str
    config_value: str
    category: str = "general"
    data_type: str = "string"
    description: str | None = None
    is_active: bool = True


class SystemConfigUpdateRequest(BaseModel):
    config_key: str | None = None
    config_value: str | None = None
    category: str | None = None
    data_type: str | None = None
    description: str | None = None
    is_active: bool | None = None


class SystemConfigItem(BaseModel):
    id: int
    config_key: str
    config_value: str
    category: str
    data_type: str
    description: str | None
    is_active: bool
    updated_by: int | None
    created_at: datetime
    updated_at: datetime | None


class SystemConfigsResponse(BaseModel):
    items: list[SystemConfigItem]
    total: int
    page: int
    page_size: int


class APIKeyCreateRequest(BaseModel):
    name: str
    description: str | None = None
    is_active: bool = True


class APIKeyUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class APIKeyItem(BaseModel):
    id: int
    name: str | None
    description: str | None
    is_active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime | None
    key_hash_preview: str


class APIKeysResponse(BaseModel):
    items: list[APIKeyItem]
    total: int
    page: int
    page_size: int


class APIKeyCreateResponse(BaseModel):
    id: int
    name: str | None
    plain_key: str
    created_at: datetime


class UserCreateRequest(BaseModel):
    username: str
    email: str | None = None
    password: str = Field(min_length=6)
    role: str = "user"
    permission_group_id: int | None = None
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    role: str | None = None
    permission_group_id: int | None = None
    is_active: bool | None = None


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=6)


class UserItem(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    permission_group_id: int | None
    permission_group_name: str | None
    is_active: bool
    created_at: datetime
    last_login: datetime | None


class UsersResponse(BaseModel):
    items: list[UserItem]
    total: int
    page: int
    page_size: int


class ToggleActiveResponse(BaseModel):
    id: int
    is_active: bool
    message: str


class MessageResponse(BaseModel):
    message: str


class LogItem(BaseModel):
    id: int
    user_id: int | None
    action: str
    detail: str | None
    ip_address: str | None
    status_code: int | None
    created_at: datetime


class LogsResponse(BaseModel):
    items: list[LogItem]
    total: int
    page: int
    page_size: int


class DiskInfo(BaseModel):
    total_gb: float
    used_gb: float
    free_gb: float


class UploadInfo(BaseModel):
    processing_count: int
    done_count: int
    failed_count: int


class DBInfo(BaseModel):
    users_count: int
    documents_count: int
    summaries_count: int


class AppInfo(BaseModel):
    version: str
    debug: bool


class SystemStatusResponse(BaseModel):
    disk: DiskInfo
    uploads: UploadInfo
    db: DBInfo
    app: AppInfo


class AdminConfigResponse(BaseModel):
    model_name: str
    model_path: str
    faiss_index_path: str
    vector_dim: int
    chunk_size: int
    chunk_overlap: int
    ocr_lang: str


class AdminConfigUpdateRequest(BaseModel):
    model_name: str | None = None
    chunk_size: int | None = Field(default=None, ge=1)
    chunk_overlap: int | None = Field(default=None, ge=0)


class BackupItem(BaseModel):
    backup_name: str
    backup_path: str
    created_at: str
    has_db_snapshot: bool | None = None
    has_db_dump: bool | None = None
    has_faiss_index: bool | None = None


class BackupResponse(BaseModel):
    backup_name: str
    backup_path: str
    created_at: str
    size_kb: float
    has_db_dump: bool
    has_faiss_index: bool


class RestoreBackupResponse(BaseModel):
    backup_name: str
    restored_at: str


def _serialize_user(item) -> UserItem:
    return UserItem(
        id=item.id,
        username=item.username,
        email=item.email,
        role=item.role,
        permission_group_id=item.permission_group_id,
        permission_group_name=item.permission_group.name if item.permission_group else None,
        is_active=item.is_active,
        created_at=item.created_at,
        last_login=item.last_login,
    )


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


@router.get("/configs", response_model=SystemConfigsResponse)
async def get_system_configs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    category: str | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemConfigsResponse:
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


@router.get("/api-keys", response_model=APIKeysResponse)
async def get_api_keys(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> APIKeysResponse:
    del admin_user
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
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> APIKeyCreateResponse:
    item, plain_key = create_api_key(db, int(admin_user["sub"]), payload.model_dump())
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
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> APIKeyItem:
    del admin_user
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
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_api_key(db, api_key_id)
    return MessageResponse(message="API key deleted")


@router.get("/permission-groups", response_model=PermissionGroupsResponse)
async def get_permission_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PermissionGroupsResponse:
    del admin_user
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
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PermissionGroupItem:
    del admin_user
    item = create_permission_group(db, payload.model_dump())
    db.refresh(item)
    return _serialize_permission_group(item)


@router.put("/permission-groups/{group_id}", response_model=PermissionGroupItem)
async def edit_permission_group(
    group_id: int,
    payload: PermissionGroupUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PermissionGroupItem:
    del admin_user
    item = update_permission_group(db, group_id, payload.model_dump(exclude_none=True))
    db.refresh(item)
    return _serialize_permission_group(item)


@router.delete("/permission-groups/{group_id}", response_model=MessageResponse)
async def remove_permission_group(
    group_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_permission_group(db, group_id)
    return MessageResponse(message="Permission group deleted")


@router.get("/system-functions", response_model=SystemFunctionsResponse)
async def get_system_functions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemFunctionsResponse:
    del admin_user
    items, total = list_system_functions(db, page, page_size, search)
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
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemFunctionItem:
    del admin_user
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


@router.put("/system-functions/{function_id}", response_model=SystemFunctionItem)
async def edit_system_function(
    function_id: int,
    payload: SystemFunctionUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemFunctionItem:
    del admin_user
    item = update_system_function(db, function_id, payload.model_dump(exclude_none=True))
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


@router.delete("/system-functions/{function_id}", response_model=MessageResponse)
async def remove_system_function(
    function_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_system_function(db, function_id)
    return MessageResponse(message="System function deleted")


@router.get("/users", response_model=UsersResponse)
async def get_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UsersResponse:
    del admin_user
    items, total = list_users(db, page, page_size, search)
    return UsersResponse(
        items=[_serialize_user(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/users", response_model=UserItem)
async def add_user(
    payload: UserCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserItem:
    del admin_user
    item = create_user(db, payload.model_dump())
    db.refresh(item)
    return _serialize_user(item)


@router.put("/users/{user_id}", response_model=UserItem)
async def edit_user(
    user_id: int,
    payload: UserUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserItem:
    del admin_user
    item = update_user(db, user_id, payload.model_dump(exclude_none=True))
    db.refresh(item)
    return _serialize_user(item)


@router.post("/users/{user_id}/reset-password", response_model=MessageResponse)
async def reset_password(
    user_id: int,
    payload: PasswordResetRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    reset_user_password(db, user_id, payload.new_password)
    return MessageResponse(message="Password reset successfully")


@router.put("/users/{user_id}/toggle-active", response_model=ToggleActiveResponse)
async def toggle_active(
    user_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ToggleActiveResponse:
    item = toggle_user_active(db, user_id, int(admin_user["sub"]))
    return ToggleActiveResponse(
        id=item.id,
        is_active=item.is_active,
        message="User status updated",
    )


@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LogsResponse:
    del admin_user
    items, total = list_logs(db, page, page_size, user_id, action, date_from, date_to)
    return LogsResponse(
        items=[
            LogItem(
                id=item.id,
                user_id=item.user_id,
                action=item.action,
                detail=item.detail,
                ip_address=item.ip_address,
                status_code=item.status_code,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/usage-logs", response_model=LogsResponse)
async def get_usage_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LogsResponse:
    return await get_logs(page, page_size, user_id, action, date_from, date_to, admin_user, db)


@router.get("/usage-logs/export")
async def export_usage_logs(
    user_id: int | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FileResponse:
    del admin_user
    path = export_logs_to_excel(db, user_id, action, date_from, date_to)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )


@router.get("/system-status", response_model=SystemStatusResponse)
async def system_status(
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemStatusResponse:
    del admin_user
    status_payload = get_system_status(db)
    return SystemStatusResponse(
        disk=DiskInfo(**status_payload["disk"]),
        uploads=UploadInfo(**status_payload["uploads"]),
        db=DBInfo(**status_payload["db"]),
        app=AppInfo(**status_payload["app"]),
    )


@router.get("/config", response_model=AdminConfigResponse)
async def get_config(
    admin_user: dict = Depends(require_admin),
) -> AdminConfigResponse:
    del admin_user
    return AdminConfigResponse(**get_safe_config())


@router.put("/config", response_model=AdminConfigResponse)
async def update_config(
    payload: AdminConfigUpdateRequest,
    admin_user: dict = Depends(require_admin),
) -> AdminConfigResponse:
    del admin_user
    return AdminConfigResponse(**update_runtime_config(payload.model_dump(exclude_none=True)))


@router.post("/backup", response_model=BackupResponse)
async def backup_now(
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BackupResponse:
    return BackupResponse(**create_backup(db, int(admin_user["sub"])))


@router.get("/backup", response_model=list[BackupItem])
async def get_backups(
    admin_user: dict = Depends(require_admin),
) -> list[BackupItem]:
    del admin_user
    return [BackupItem(**item) for item in list_backups()]


@router.post("/backup/{backup_name}/restore", response_model=RestoreBackupResponse)
async def restore_backup_data(
    backup_name: str,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RestoreBackupResponse:
    result = restore_backup(db, backup_name, int(admin_user["sub"]))
    return RestoreBackupResponse(
        backup_name=result["backup_name"],
        restored_at=result["restored_at"],
    )
