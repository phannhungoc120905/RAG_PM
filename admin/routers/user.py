from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from db.database import get_db
from auth.dependencies import require_active_user
from db.models import User
from admin.service import (
    create_user,
    list_users,
    update_user,
    reset_user_password,
    toggle_user_active,
    list_login_history
)
from admin.schemas import (
    UserCreateRequest,
    UserUpdateRequest,
    PasswordResetRequest,
    UserItem,
    UsersResponse,
    ToggleActiveResponse,
    LoginHistoryResponse,
    LoginHistoryItem,
    MessageResponse
)

router = APIRouter(prefix="/users", tags=["User Management"])

def _require_agency_leader(user: User) -> None:
    if user.role == "admin":
        return
    if not user.permission_group or user.permission_group.code not in {"ADMIN", "AGENCY_LEADER"}:
        raise HTTPException(
            status_code=403,
            detail="Only admin or agency leader can manage business users",
        )

def _serialize_user(item) -> UserItem:
    return UserItem(
        id=item.id,
        username=item.username,
        email=item.email,
        role=item.role,
        permission_group_id=item.permission_group_id,
        permission_group_name=item.permission_group.name if item.permission_group else None,
        department_id=item.department_id,
        department_name=item.department.name if item.department else None,
        position_id=item.position_id,
        position_name=item.position.name if item.position else None,
        auth_source=item.auth_source,
        is_active=item.is_active,
        created_at=item.created_at,
        last_login=item.last_login,
    )

@router.get("", response_model=UsersResponse)
async def get_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    role: str | None = None,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> UsersResponse:
    _require_agency_leader(current_user)
    items, total = list_users(db, page, page_size, search, role)
    return UsersResponse(
        items=[_serialize_user(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.post("", response_model=UserItem)
async def add_user(
    payload: UserCreateRequest,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> UserItem:
    _require_agency_leader(current_user)
    item = create_user(db, payload.model_dump())
    return _serialize_user(item)

@router.put("/{user_id}", response_model=UserItem)
async def edit_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> UserItem:
    _require_agency_leader(current_user)
    item = update_user(db, user_id, payload.model_dump(exclude_none=True))
    return _serialize_user(item)

@router.post("/{user_id}/reset-password", response_model=MessageResponse)
async def reset_password(
    user_id: int,
    payload: PasswordResetRequest,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    _require_agency_leader(current_user)
    reset_user_password(db, user_id, payload.new_password)
    return MessageResponse(message="Password reset successfully")

@router.post("/{user_id}/toggle-active", response_model=ToggleActiveResponse)
async def toggle_active(
    user_id: int,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> ToggleActiveResponse:
    _require_agency_leader(current_user)
    is_active = toggle_user_active(db, user_id)
    return ToggleActiveResponse(
        id=user_id,
        is_active=is_active,
        message=f"User {'activated' if is_active else 'deactivated'} successfully"
    )

@router.get("/login-history", response_model=LoginHistoryResponse)
async def get_login_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    user_id: int | None = None,
    login_type: str | None = None,
    status_value: str | None = None,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> LoginHistoryResponse:
    _require_agency_leader(current_user)
    items, total = list_login_history(
        db,
        page=page,
        page_size=page_size,
        search=search,
        user_id=user_id,
        login_type=login_type,
        status_value=status_value,
    )
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
    )
