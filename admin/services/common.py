from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from db.models import User, Department, IssuingUnit, Position, PermissionGroup, SystemFunction, SystemConfig, APIKey, WorkAssignmentDocument, WorkItem, NoticeDocument

def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def _get_department_or_404(db: Session, department_id: int) -> Department:
    item = db.get(Department, department_id)
    if not item:
        raise HTTPException(status_code=404, detail="Department not found")
    return item

def _get_issuing_unit_or_404(db: Session, unit_id: int) -> IssuingUnit:
    item = db.get(IssuingUnit, unit_id)
    if not item:
        raise HTTPException(status_code=404, detail="Issuing unit not found")
    return item

def _get_position_or_404(db: Session, position_id: int) -> Position:
    item = db.get(Position, position_id)
    if not item:
        raise HTTPException(status_code=404, detail="Position not found")
    return item

def _get_group_or_404(db: Session, group_id: int) -> PermissionGroup:
    group = db.get(PermissionGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Permission group not found")
    return group

def _get_function_or_404(db: Session, function_id: int) -> SystemFunction:
    function = db.get(SystemFunction, function_id)
    if not function:
        raise HTTPException(status_code=404, detail="System function not found")
    return function

def _get_config_or_404(db: Session, config_id: int) -> SystemConfig:
    config = db.get(SystemConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config

def _get_api_key_or_404(db: Session, api_key_id: int) -> APIKey:
    api_key = db.get(APIKey, api_key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    return api_key

def _get_work_document_or_404(db: Session, document_id: int) -> WorkAssignmentDocument:
    item = db.get(WorkAssignmentDocument, document_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work document not found")
    return item

def _get_work_item_or_404(db: Session, item_id: int) -> WorkItem:
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    return item

def _get_notice_document_or_404(db: Session, notice_id: int) -> NoticeDocument:
    item = db.get(NoticeDocument, notice_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notice document not found")
    return item
