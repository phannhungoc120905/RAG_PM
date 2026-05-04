from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from auth.service import decode_token
from db.database import get_db
from db.models import User


security = HTTPBearer()


async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    return decode_token(token.credentials)


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def require_active_user(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    db_user = db.get(User, int(user["sub"]))
    if not db_user or not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive or missing user",
        )
    return db_user
