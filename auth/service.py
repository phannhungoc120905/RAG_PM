from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from db.models import User


ALGORITHM = "HS256"


def _get_pwd_context():
    from passlib.context import CryptContext

    return CryptContext(schemes=["bcrypt"], deprecated="auto")


def _get_jwt_module():
    from jose import jwt

    return jwt


def _get_jwt_exceptions():
    from jose import ExpiredSignatureError, JWTError

    return ExpiredSignatureError, JWTError


def hash_password(password: str) -> str:
    return _get_pwd_context().hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _get_pwd_context().verify(plain, hashed)


def create_access_token(data: dict[str, Any]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(data["sub"]),
        "username": data["username"],
        "role": data["role"],
        "exp": expire,
    }
    if data.get("session_id"):
        payload["session_id"] = data["session_id"]
    return _get_jwt_module().encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )
    ExpiredSignatureError, JWTError = _get_jwt_exceptions()
    try:
        payload = _get_jwt_module().decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        raise credentials_error from exc
    except JWTError as exc:
        raise credentials_error from exc

    required_fields = {"sub", "username", "role", "exp"}
    if not required_fields.issubset(payload):
        raise credentials_error
    return payload


async def get_user_by_username(username: str, db: Session) -> User | None:
    statement = select(User).where(User.username == username)
    return db.scalar(statement)


async def get_user_by_sso_subject(sso_subject: str, db: Session) -> User | None:
    statement = select(User).where(User.sso_subject == sso_subject)
    return db.scalar(statement)


async def authenticate_user(username: str, password: str, db: Session) -> User | None:
    user = await get_user_by_username(username, db)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user
