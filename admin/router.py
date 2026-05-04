<<<<<<< HEAD
from datetime import datetime
=======
from datetime import date, datetime
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from admin.service import (
    create_api_key,
    create_backup,
<<<<<<< HEAD
    create_permission_group,
    create_system_config,
    create_system_function,
    create_user,
    delete_api_key,
    delete_permission_group,
    delete_system_config,
    delete_system_function,
=======
    create_department,
    create_issuing_unit,
    create_notice_document,
    create_permission_group,
    create_position,
    create_system_config,
    create_system_function,
    create_user,
    create_work_document,
    create_work_item,
    delete_api_key,
    delete_department,
    delete_issuing_unit,
    delete_notice_document,
    delete_permission_group,
    delete_position,
    delete_system_config,
    delete_system_function,
    delete_work_document,
    delete_work_item,
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
    export_logs_to_excel,
    get_safe_config,
    get_system_status,
    list_api_keys,
    list_backups,
<<<<<<< HEAD
    list_logs,
    list_permission_groups,
    list_system_configs,
    list_system_functions,
    list_users,
=======
    list_departments,
    list_issuing_units,
    list_login_history,
    list_logs,
    list_notice_documents,
    list_permission_groups,
    list_positions,
    list_system_configs,
    list_system_functions,
    list_users,
    list_work_documents,
    list_work_items,
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
    reset_user_password,
    restore_backup,
    toggle_user_active,
    update_api_key,
<<<<<<< HEAD
    update_permission_group,
=======
    update_department,
    update_issuing_unit,
    update_notice_document,
    update_permission_group,
    update_position,
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
    update_runtime_config,
    update_system_config,
    update_system_function,
    update_user,
<<<<<<< HEAD
=======
    update_work_document,
    update_work_item,
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
)
from auth.dependencies import require_admin
from db.database import get_db


router = APIRouter()


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
<<<<<<< HEAD
=======
    department_id: int | None = None
    position_id: int | None = None
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    role: str | None = None
    permission_group_id: int | None = None
<<<<<<< HEAD
=======
    department_id: int | None = None
    position_id: int | None = None
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
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
<<<<<<< HEAD
=======
    department_id: int | None
    department_name: str | None
    position_id: int | None
    position_name: str | None
    auth_source: str
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
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


<<<<<<< HEAD
=======
class LoginHistoryItem(BaseModel):
    id: int
    user_id: int | None
    username_snapshot: str
    login_type: str
    session_id: str
    login_at: datetime
    logout_at: datetime | None
    status: str
    ip_address: str | None
    detail: str | None


class LoginHistoryResponse(BaseModel):
    items: list[LoginHistoryItem]
    total: int
    page: int
    page_size: int


class NamedListResponse(BaseModel):
    total: int
    page: int
    page_size: int


>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
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


<<<<<<< HEAD
=======
class IssuingUnitCreateRequest(BaseModel):
    code: str
    name: str
    short_name: str | None = None
    parent_id: int | None = None
    address: str | None = None
    is_active: bool = True


class IssuingUnitUpdateRequest(BaseModel):
    code: str | None = None
    name: str | None = None
    short_name: str | None = None
    parent_id: int | None = None
    address: str | None = None
    is_active: bool | None = None


class IssuingUnitItem(BaseModel):
    id: int
    code: str
    name: str
    short_name: str | None
    parent_id: int | None
    parent_name: str | None
    address: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None


class IssuingUnitsResponse(BaseModel):
    items: list[IssuingUnitItem]
    total: int
    page: int
    page_size: int


class DepartmentCreateRequest(BaseModel):
    code: str
    name: str
    issuing_unit_id: int | None = None
    parent_id: int | None = None
    description: str | None = None
    is_active: bool = True


class DepartmentUpdateRequest(BaseModel):
    code: str | None = None
    name: str | None = None
    issuing_unit_id: int | None = None
    parent_id: int | None = None
    description: str | None = None
    is_active: bool | None = None


class DepartmentItem(BaseModel):
    id: int
    code: str
    name: str
    issuing_unit_id: int | None
    issuing_unit_name: str | None
    parent_id: int | None
    parent_name: str | None
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None


class DepartmentsResponse(BaseModel):
    items: list[DepartmentItem]
    total: int
    page: int
    page_size: int


class PositionCreateRequest(BaseModel):
    code: str
    name: str
    department_id: int | None = None
    description: str | None = None
    is_active: bool = True


class PositionUpdateRequest(BaseModel):
    code: str | None = None
    name: str | None = None
    department_id: int | None = None
    description: str | None = None
    is_active: bool | None = None


class PositionItem(BaseModel):
    id: int
    code: str
    name: str
    department_id: int | None
    department_name: str | None
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None


class PositionsResponse(BaseModel):
    items: list[PositionItem]
    total: int
    page: int
    page_size: int


class WorkDocumentCreateRequest(BaseModel):
    document_code: str
    title: str
    content_summary: str | None = None
    issuing_unit_id: int | None = None
    department_id: int | None = None
    assigned_by_user_id: int | None = None
    assigned_department_id: int | None = None
    due_date: date | None = None
    status: str = "draft"


class WorkDocumentUpdateRequest(BaseModel):
    document_code: str | None = None
    title: str | None = None
    content_summary: str | None = None
    issuing_unit_id: int | None = None
    department_id: int | None = None
    assigned_by_user_id: int | None = None
    assigned_department_id: int | None = None
    due_date: date | None = None
    status: str | None = None


class WorkDocumentItem(BaseModel):
    id: int
    document_code: str
    title: str
    content_summary: str | None
    issuing_unit_id: int | None
    issuing_unit_name: str | None
    department_id: int | None
    department_name: str | None
    assigned_by_user_id: int | None
    assigned_by_username: str | None
    assigned_department_id: int | None
    assigned_department_name: str | None
    due_date: date | None
    status: str
    work_item_count: int
    created_at: datetime
    updated_at: datetime | None


class WorkDocumentsResponse(BaseModel):
    items: list[WorkDocumentItem]
    total: int
    page: int
    page_size: int


class WorkItemCreateRequest(BaseModel):
    work_document_id: int
    title: str
    description: str | None = None
    assignee_user_id: int | None = None
    department_id: int | None = None
    position_id: int | None = None
    priority: str = "normal"
    status: str = "pending"
    due_date: date | None = None


class WorkItemUpdateRequest(BaseModel):
    work_document_id: int | None = None
    title: str | None = None
    description: str | None = None
    assignee_user_id: int | None = None
    department_id: int | None = None
    position_id: int | None = None
    priority: str | None = None
    status: str | None = None
    due_date: date | None = None


class WorkItemEntry(BaseModel):
    id: int
    work_document_id: int
    work_document_code: str | None
    title: str
    description: str | None
    assignee_user_id: int | None
    assignee_username: str | None
    department_id: int | None
    department_name: str | None
    position_id: int | None
    position_name: str | None
    priority: str
    status: str
    due_date: date | None
    created_at: datetime
    updated_at: datetime | None


class WorkItemsResponse(BaseModel):
    items: list[WorkItemEntry]
    total: int
    page: int
    page_size: int


class NoticeDocumentCreateRequest(BaseModel):
    notice_code: str
    title: str
    content: str | None = None
    issuing_unit_id: int | None = None
    department_id: int | None = None
    posted_by_user_id: int | None = None
    effective_date: date | None = None
    status: str = "draft"


class NoticeDocumentUpdateRequest(BaseModel):
    notice_code: str | None = None
    title: str | None = None
    content: str | None = None
    issuing_unit_id: int | None = None
    department_id: int | None = None
    posted_by_user_id: int | None = None
    effective_date: date | None = None
    status: str | None = None


class NoticeDocumentItem(BaseModel):
    id: int
    notice_code: str
    title: str
    content: str | None
    issuing_unit_id: int | None
    issuing_unit_name: str | None
    department_id: int | None
    department_name: str | None
    posted_by_user_id: int | None
    posted_by_username: str | None
    effective_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime | None


class NoticeDocumentsResponse(BaseModel):
    items: list[NoticeDocumentItem]
    total: int
    page: int
    page_size: int


>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
def _serialize_user(item) -> UserItem:
    return UserItem(
        id=item.id,
        username=item.username,
        email=item.email,
        role=item.role,
        permission_group_id=item.permission_group_id,
        permission_group_name=item.permission_group.name if item.permission_group else None,
<<<<<<< HEAD
=======
        department_id=item.department_id,
        department_name=item.department.name if item.department else None,
        position_id=item.position_id,
        position_name=item.position.name if item.position else None,
        auth_source=item.auth_source,
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
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


<<<<<<< HEAD
=======
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


def _serialize_notice_document(item) -> NoticeDocumentItem:
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


>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
@router.get("/configs", response_model=SystemConfigsResponse)
async def get_system_configs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    category: str | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemConfigsResponse:
<<<<<<< HEAD
=======
    del admin_user
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
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
<<<<<<< HEAD
    item = update_system_config(
        db,
        config_id,
        int(admin_user["sub"]),
        payload.model_dump(exclude_none=True),
    )
=======
    item = update_system_config(db, config_id, int(admin_user["sub"]), payload.model_dump(exclude_none=True))
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
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
<<<<<<< HEAD
    return APIKeyCreateResponse(
        id=item.id,
        name=item.name,
        plain_key=plain_key,
        created_at=item.created_at,
    )
=======
    return APIKeyCreateResponse(id=item.id, name=item.name, plain_key=plain_key, created_at=item.created_at)
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec


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
<<<<<<< HEAD
    return PermissionGroupsResponse(
        items=[_serialize_permission_group(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
=======
    return PermissionGroupsResponse(items=[_serialize_permission_group(item) for item in items], total=total, page=page, page_size=page_size)
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec


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
<<<<<<< HEAD
    return UsersResponse(
        items=[_serialize_user(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
=======
    return UsersResponse(items=[_serialize_user(item) for item in items], total=total, page=page, page_size=page_size)
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec


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
<<<<<<< HEAD
    return ToggleActiveResponse(
        id=item.id,
        is_active=item.is_active,
        message="User status updated",
    )
=======
    return ToggleActiveResponse(id=item.id, is_active=item.is_active, message="User status updated")
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec


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
<<<<<<< HEAD
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
=======
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=path.name)


@router.get("/login-history", response_model=LoginHistoryResponse)
async def get_login_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    user_id: int | None = None,
    login_type: str | None = None,
    status_value: str | None = Query(default=None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LoginHistoryResponse:
    del admin_user
    items, total = list_login_history(db, page, page_size, search, user_id, login_type, status_value, date_from, date_to)
    return LoginHistoryResponse(
        items=[
            LoginHistoryItem(
                id=item.id,
                user_id=item.user_id,
                username_snapshot=item.username_snapshot,
                login_type=item.login_type,
                session_id=item.session_id,
                login_at=item.login_at,
                logout_at=item.logout_at,
                status=item.status,
                ip_address=item.ip_address,
                detail=item.detail,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
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
<<<<<<< HEAD
async def get_config(
    admin_user: dict = Depends(require_admin),
) -> AdminConfigResponse:
=======
async def get_config(admin_user: dict = Depends(require_admin)) -> AdminConfigResponse:
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
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
<<<<<<< HEAD
async def get_backups(
    admin_user: dict = Depends(require_admin),
) -> list[BackupItem]:
=======
async def get_backups(admin_user: dict = Depends(require_admin)) -> list[BackupItem]:
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
    del admin_user
    return [BackupItem(**item) for item in list_backups()]


@router.post("/backup/{backup_name}/restore", response_model=RestoreBackupResponse)
async def restore_backup_data(
    backup_name: str,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RestoreBackupResponse:
    result = restore_backup(db, backup_name, int(admin_user["sub"]))
<<<<<<< HEAD
    return RestoreBackupResponse(
        backup_name=result["backup_name"],
        restored_at=result["restored_at"],
    )
=======
    return RestoreBackupResponse(backup_name=result["backup_name"], restored_at=result["restored_at"])


@router.get("/issuing-units", response_model=IssuingUnitsResponse)
async def get_issuing_units(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    is_active: bool | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IssuingUnitsResponse:
    del admin_user
    items, total = list_issuing_units(db, page, page_size, search, is_active)
    return IssuingUnitsResponse(items=[_serialize_issuing_unit(item) for item in items], total=total, page=page, page_size=page_size)


@router.post("/issuing-units", response_model=IssuingUnitItem)
async def add_issuing_unit(
    payload: IssuingUnitCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IssuingUnitItem:
    del admin_user
    return _serialize_issuing_unit(create_issuing_unit(db, payload.model_dump()))


@router.put("/issuing-units/{unit_id}", response_model=IssuingUnitItem)
async def edit_issuing_unit(
    unit_id: int,
    payload: IssuingUnitUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IssuingUnitItem:
    del admin_user
    return _serialize_issuing_unit(update_issuing_unit(db, unit_id, payload.model_dump(exclude_none=True)))


@router.delete("/issuing-units/{unit_id}", response_model=MessageResponse)
async def remove_issuing_unit(
    unit_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_issuing_unit(db, unit_id)
    return MessageResponse(message="Issuing unit deleted")


@router.get("/departments", response_model=DepartmentsResponse)
async def get_departments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    issuing_unit_id: int | None = None,
    is_active: bool | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DepartmentsResponse:
    del admin_user
    items, total = list_departments(db, page, page_size, search, issuing_unit_id, is_active)
    return DepartmentsResponse(items=[_serialize_department(item) for item in items], total=total, page=page, page_size=page_size)


@router.post("/departments", response_model=DepartmentItem)
async def add_department(
    payload: DepartmentCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DepartmentItem:
    del admin_user
    return _serialize_department(create_department(db, payload.model_dump()))


@router.put("/departments/{department_id}", response_model=DepartmentItem)
async def edit_department(
    department_id: int,
    payload: DepartmentUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DepartmentItem:
    del admin_user
    return _serialize_department(update_department(db, department_id, payload.model_dump(exclude_none=True)))


@router.delete("/departments/{department_id}", response_model=MessageResponse)
async def remove_department(
    department_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_department(db, department_id)
    return MessageResponse(message="Department deleted")


@router.get("/positions", response_model=PositionsResponse)
async def get_positions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    department_id: int | None = None,
    is_active: bool | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PositionsResponse:
    del admin_user
    items, total = list_positions(db, page, page_size, search, department_id, is_active)
    return PositionsResponse(items=[_serialize_position(item) for item in items], total=total, page=page, page_size=page_size)


@router.post("/positions", response_model=PositionItem)
async def add_position(
    payload: PositionCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PositionItem:
    del admin_user
    return _serialize_position(create_position(db, payload.model_dump()))


@router.put("/positions/{position_id}", response_model=PositionItem)
async def edit_position(
    position_id: int,
    payload: PositionUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PositionItem:
    del admin_user
    return _serialize_position(update_position(db, position_id, payload.model_dump(exclude_none=True)))


@router.delete("/positions/{position_id}", response_model=MessageResponse)
async def remove_position(
    position_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_position(db, position_id)
    return MessageResponse(message="Position deleted")


@router.get("/work-documents", response_model=WorkDocumentsResponse)
async def get_work_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    status_value: str | None = Query(default=None, alias="status"),
    issuing_unit_id: int | None = None,
    department_id: int | None = None,
    assigned_department_id: int | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkDocumentsResponse:
    del admin_user
    items, total = list_work_documents(db, page, page_size, search, status_value, issuing_unit_id, department_id, assigned_department_id)
    return WorkDocumentsResponse(items=[_serialize_work_document(item) for item in items], total=total, page=page, page_size=page_size)


@router.post("/work-documents", response_model=WorkDocumentItem)
async def add_work_document(
    payload: WorkDocumentCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkDocumentItem:
    del admin_user
    return _serialize_work_document(create_work_document(db, payload.model_dump()))


@router.put("/work-documents/{document_id}", response_model=WorkDocumentItem)
async def edit_work_document(
    document_id: int,
    payload: WorkDocumentUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkDocumentItem:
    del admin_user
    return _serialize_work_document(update_work_document(db, document_id, payload.model_dump(exclude_none=True)))


@router.delete("/work-documents/{document_id}", response_model=MessageResponse)
async def remove_work_document(
    document_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_work_document(db, document_id)
    return MessageResponse(message="Work document deleted")


@router.get("/work-items", response_model=WorkItemsResponse)
async def get_work_items(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    status_value: str | None = Query(default=None, alias="status"),
    work_document_id: int | None = None,
    assignee_user_id: int | None = None,
    department_id: int | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkItemsResponse:
    del admin_user
    items, total = list_work_items(db, page, page_size, search, status_value, work_document_id, assignee_user_id, department_id)
    return WorkItemsResponse(items=[_serialize_work_item(item) for item in items], total=total, page=page, page_size=page_size)


@router.post("/work-items", response_model=WorkItemEntry)
async def add_work_item(
    payload: WorkItemCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkItemEntry:
    del admin_user
    return _serialize_work_item(create_work_item(db, payload.model_dump()))


@router.put("/work-items/{item_id}", response_model=WorkItemEntry)
async def edit_work_item(
    item_id: int,
    payload: WorkItemUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WorkItemEntry:
    del admin_user
    return _serialize_work_item(update_work_item(db, item_id, payload.model_dump(exclude_none=True)))


@router.delete("/work-items/{item_id}", response_model=MessageResponse)
async def remove_work_item(
    item_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_work_item(db, item_id)
    return MessageResponse(message="Work item deleted")


@router.get("/notice-documents", response_model=NoticeDocumentsResponse)
async def get_notice_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    status_value: str | None = Query(default=None, alias="status"),
    issuing_unit_id: int | None = None,
    department_id: int | None = None,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> NoticeDocumentsResponse:
    del admin_user
    items, total = list_notice_documents(db, page, page_size, search, status_value, issuing_unit_id, department_id)
    return NoticeDocumentsResponse(items=[_serialize_notice_document(item) for item in items], total=total, page=page, page_size=page_size)


@router.post("/notice-documents", response_model=NoticeDocumentItem)
async def add_notice_document(
    payload: NoticeDocumentCreateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> NoticeDocumentItem:
    del admin_user
    return _serialize_notice_document(create_notice_document(db, payload.model_dump()))


@router.put("/notice-documents/{notice_id}", response_model=NoticeDocumentItem)
async def edit_notice_document(
    notice_id: int,
    payload: NoticeDocumentUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> NoticeDocumentItem:
    del admin_user
    return _serialize_notice_document(update_notice_document(db, notice_id, payload.model_dump(exclude_none=True)))


@router.delete("/notice-documents/{notice_id}", response_model=MessageResponse)
async def remove_notice_document(
    notice_id: int,
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del admin_user
    delete_notice_document(db, notice_id)
    return MessageResponse(message="Notice document deleted")
>>>>>>> 9709d26f9ea0d522d85f3bbb56c87f59687901ec
