from datetime import date, datetime
from pydantic import BaseModel, Field

# --- Auth & Permissions ---
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

# --- API Keys ---
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

# --- User Management ---
class UserCreateRequest(BaseModel):
    username: str
    email: str | None = None
    password: str = Field(min_length=6)
    department_id: int | None = None
    position_id: int | None = None
    is_active: bool = True

class UserUpdateRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    department_id: int | None = None
    position_id: int | None = None
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
    department_id: int | None
    department_name: str | None
    position_id: int | None
    position_name: str | None
    auth_source: str
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

# --- System Configuration ---
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

# --- System Status ---
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

# --- Backup & Logs ---
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

# --- Organizational Entities ---
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

# --- Work Management ---
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

# --- Notice Documents ---
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

# --- Common ---
class MessageResponse(BaseModel):
    message: str

class NamedListResponse(BaseModel):
    total: int
    page: int
    page_size: int
