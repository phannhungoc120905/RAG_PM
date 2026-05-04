from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user, require_active_user
from auth.service import authenticate_user, create_access_token
from db.database import get_db
from db.models import SystemLog, User


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


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
    is_active: bool
    created_at: datetime
    last_login: datetime | None


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


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    user = await authenticate_user(payload.username, payload.password, db)
    if not user or not user.is_active:
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

    token = create_access_token(
        {"sub": user.id, "username": user.username, "role": user.role}
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

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserInfo(id=user.id, username=user.username, role=user.role),
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LogoutResponse:
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
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
    )
