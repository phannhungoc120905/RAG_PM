import json
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user, require_active_user
from auth.service import (
    authenticate_user,
    create_access_token,
    get_user_by_sso_subject,
    hash_password,
)
from config import settings
from db.database import get_db
from db.models import LoginHistory, SystemLog, User


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class SSOLoginRequest(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    sso_subject: str
    shared_secret: str


class UserInfo(BaseModel):
    id: int
    username: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserInfo


class LogoutResponse(BaseModel):
    message: str


class MeResponse(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    permission_group_id: int | None
    permission_group_code: str | None
    permission_group_name: str | None
    is_active: bool
    created_at: datetime
    last_login: datetime | None
    auth_source: str
    department_id: int | None
    department_name: str | None
    position_id: int | None
    position_name: str | None


def _write_system_log(
    db: Session,
    action: str,
    request: Request,
    status_code: int,
    user_id: int | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        SystemLog(
            user_id=user_id,
            action=action,
            detail=detail,
            ip_address=request.client.host if request.client else None,
            status_code=status_code,
        )
    )
    db.commit()


def _create_login_history(
    db: Session,
    user: User | None,
    username_snapshot: str,
    request: Request,
    login_type: str,
    status_value: str,
    detail: str | None = None,
) -> str:
    session_id = secrets.token_urlsafe(24)
    db.add(
        LoginHistory(
            user_id=user.id if user else None,
            username_snapshot=username_snapshot,
            login_type=login_type,
            session_id=session_id,
            status=status_value,
            ip_address=request.client.host if request.client else None,
            detail=detail,
        )
    )
    db.commit()
    return session_id


def _mark_logout(db: Session, session_id: str | None) -> None:
    if not session_id:
        return
    record = db.scalar(select(LoginHistory).where(LoginHistory.session_id == session_id))
    if not record:
        return
    record.logout_at = datetime.utcnow()
    db.add(record)
    db.commit()


def _build_login_response(user: User, session_id: str) -> LoginResponse:
    token = create_access_token(
        {
            "sub": user.id,
            "username": user.username,
            "role": user.role,
            "session_id": session_id,
        }
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserInfo(id=user.id, username=user.username, role=user.role),
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    user = await authenticate_user(payload.username, payload.password, db)
    if not user or not user.is_active:
        _create_login_history(
            db,
            user=None,
            username_snapshot=payload.username,
            request=request,
            login_type="local",
            status_value="failed",
            detail="invalid_credentials",
        )
        _write_system_log(
            db,
            action="login",
            request=request,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"username={payload.username}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_id = _create_login_history(
        db,
        user=user,
        username_snapshot=user.username,
        request=request,
        login_type="local",
        status_value="success",
    )
    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    _write_system_log(
        db,
        action="login",
        request=request,
        status_code=status.HTTP_200_OK,
        user_id=user.id,
    )

    return _build_login_response(user, session_id)


@router.post("/sso/login", response_model=LoginResponse)
async def sso_login(
    payload: SSOLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    if not settings.SSO_ENABLED:
        raise HTTPException(status_code=503, detail="SSO is disabled")
    if payload.shared_secret != settings.SSO_SHARED_SECRET:
        _create_login_history(
            db,
            user=None,
            username_snapshot=payload.username,
            request=request,
            login_type="sso",
            status_value="failed",
            detail="invalid_shared_secret",
        )
        raise HTTPException(status_code=401, detail="Invalid SSO shared secret")

    user = await get_user_by_sso_subject(payload.sso_subject, db)
    if not user:
        user = db.scalar(select(User).where(User.username == payload.username))
    if not user and payload.email:
        user = db.scalar(select(User).where(User.email == payload.email))

    if not user:
        if not settings.SSO_AUTO_CREATE_USERS:
            raise HTTPException(status_code=404, detail="SSO user is not provisioned")
        user = User(
            username=payload.username,
            email=payload.email,
            hashed_password=hash_password(secrets.token_urlsafe(20)),
            role="user",
            sso_subject=payload.sso_subject,
            auth_source="sso",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.email = payload.email or user.email
        user.sso_subject = payload.sso_subject
        user.auth_source = "sso"
        db.add(user)
        db.commit()
        db.refresh(user)

    if not user.is_active:
        _create_login_history(
            db,
            user=user,
            username_snapshot=user.username,
            request=request,
            login_type="sso",
            status_value="failed",
            detail="inactive_user",
        )
        raise HTTPException(status_code=401, detail="Inactive or missing user")

    session_id = _create_login_history(
        db,
        user=user,
        username_snapshot=user.username,
        request=request,
        login_type="sso",
        status_value="success",
        detail=json.dumps(
            {
                "provider": settings.SSO_PROVIDER_NAME,
                "full_name": payload.full_name,
            },
            ensure_ascii=False,
        ),
    )
    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    _write_system_log(
        db,
        action="login_sso",
        request=request,
        status_code=status.HTTP_200_OK,
        user_id=user.id,
        detail=json.dumps({"provider": settings.SSO_PROVIDER_NAME}, ensure_ascii=False),
    )
    return _build_login_response(user, session_id)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    _mark_logout(db, current_user.get("session_id"))
    _write_system_log(
        db,
        action="logout",
        request=request,
        status_code=status.HTTP_200_OK,
        user_id=int(current_user["sub"]),
    )
    return LogoutResponse(message="Logged out")


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(require_active_user)) -> MeResponse:
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        permission_group_id=current_user.permission_group_id,
        permission_group_code=current_user.permission_group.code if current_user.permission_group else None,
        permission_group_name=current_user.permission_group.name if current_user.permission_group else None,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        auth_source=current_user.auth_source,
        department_id=current_user.department_id,
        department_name=current_user.department.name if current_user.department else None,
        position_id=current_user.position_id,
        position_name=current_user.position.name if current_user.position else None,
    )
