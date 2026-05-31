from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from auth.service import decode_token
from db.database import get_db
from db.models import ActionFunctionMapping, PermissionGroupFunction, User
from sqlalchemy import select


security = HTTPBearer()


AGENCY_LEADER_EXTRA_ACTIONS = {
    "admin.entities.departments.list",
    "admin.entities.positions.list",
    "admin.entities.issuing_units.list",
    "api.supported_formats.view",
    "api.upload.create",
    "ocr.supported_formats.view",
    "ocr.extract_text.create",
    "ocr.analyze.create",
    "ocr.analyze_text.create",
    "ocr.upload_process.create",
    "ocr.search.create",
}


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


def require_action(action_key: str):
    async def _check(
        current_user: User = Depends(require_active_user),
        db: Session = Depends(get_db),
    ) -> User:
        if current_user.role == "admin":
            return current_user
        if (
            current_user.permission_group
            and current_user.permission_group.code == "AGENCY_LEADER"
            and action_key in AGENCY_LEADER_EXTRA_ACTIONS
        ):
            return current_user

        mappings = list(
            db.scalars(
                select(ActionFunctionMapping)
                .where(ActionFunctionMapping.action_key == action_key)
                .where(ActionFunctionMapping.is_active.is_(True))
            ).all()
        )
        if not mappings:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Action is not configured",
            )
        if not current_user.permission_group_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission group is required",
            )

        function_ids = [mapping.function_id for mapping in mappings]
        permissions = list(
            db.scalars(
                select(PermissionGroupFunction)
                .where(PermissionGroupFunction.group_id == current_user.permission_group_id)
                .where(PermissionGroupFunction.function_id.in_(function_ids))
            ).all()
        )
        if not permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )

        permission_by_function = {perm.function_id: perm for perm in permissions}
        for mapping in mappings:
            perm = permission_by_function.get(mapping.function_id)
            if not perm:
                continue
            if mapping.action_type == "view" and perm.can_view:
                return current_user
            if mapping.action_type == "create" and perm.can_create:
                return current_user
            if mapping.action_type == "update" and perm.can_update:
                return current_user
            if mapping.action_type == "delete" and perm.can_delete:
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    return _check
