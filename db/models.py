from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


class PermissionGroup(Base):
    __tablename__ = "permission_groups"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    users: Mapped[list[User]] = relationship("User", back_populates="permission_group")
    function_permissions: Mapped[list[PermissionGroupFunction]] = relationship(
        "PermissionGroupFunction",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class SystemFunction(Base):
    __tablename__ = "system_functions"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    module: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    group_permissions: Mapped[list[PermissionGroupFunction]] = relationship(
        "PermissionGroupFunction",
        back_populates="function",
        cascade="all, delete-orphan",
    )


class PermissionGroupFunction(Base):
    __tablename__ = "permission_group_functions"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("permission_groups.id"), nullable=False)
    function_id: Mapped[int] = mapped_column(ForeignKey("system_functions.id"), nullable=False)
    can_view: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    can_create: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_update: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_delete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    group: Mapped[PermissionGroup] = relationship("PermissionGroup", back_populates="function_permissions")
    function: Mapped[SystemFunction] = relationship("SystemFunction", back_populates="group_permissions")


class IssuingUnit(Base):
    __tablename__ = "issuing_units"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("issuing_units.id"), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    parent: Mapped[Optional[IssuingUnit]] = relationship("IssuingUnit", remote_side=[id], back_populates="children")
    children: Mapped[list[IssuingUnit]] = relationship("IssuingUnit", back_populates="parent")
    departments: Mapped[list[Department]] = relationship("Department", back_populates="issuing_unit")
    work_assignment_documents: Mapped[list[WorkAssignmentDocument]] = relationship(
        "WorkAssignmentDocument",
        back_populates="issuing_unit",
    )
    notice_documents: Mapped[list[NoticeDocument]] = relationship("NoticeDocument", back_populates="issuing_unit")


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    issuing_unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("issuing_units.id"), nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    issuing_unit: Mapped[Optional[IssuingUnit]] = relationship("IssuingUnit", back_populates="departments")
    parent: Mapped[Optional[Department]] = relationship("Department", remote_side=[id], back_populates="children")
    children: Mapped[list[Department]] = relationship("Department", back_populates="parent")
    positions: Mapped[list[Position]] = relationship("Position", back_populates="department")
    users: Mapped[list[User]] = relationship("User", back_populates="department")
    work_assignment_documents: Mapped[list[WorkAssignmentDocument]] = relationship(
        "WorkAssignmentDocument",
        back_populates="department",
        foreign_keys="WorkAssignmentDocument.department_id",
    )
    assigned_work_documents: Mapped[list[WorkAssignmentDocument]] = relationship(
        "WorkAssignmentDocument",
        back_populates="assigned_department",
        foreign_keys="WorkAssignmentDocument.assigned_department_id",
    )
    work_items: Mapped[list[WorkItem]] = relationship("WorkItem", back_populates="department")
    notice_documents: Mapped[list[NoticeDocument]] = relationship("NoticeDocument", back_populates="department")


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    department: Mapped[Optional[Department]] = relationship("Department", back_populates="positions")
    users: Mapped[list[User]] = relationship("User", back_populates="position")
    work_items: Mapped[list[WorkItem]] = relationship("WorkItem", back_populates="position")


class LoginHistory(Base):
    __tablename__ = "login_history"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    username_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    login_type: Mapped[str] = mapped_column(String(50), nullable=False, default="local", server_default="local")
    session_id: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    login_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    logout_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="success", server_default="success")
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped[Optional[User]] = relationship("User", back_populates="login_history_records")


class SystemConfig(Base):
    __tablename__ = "system_configs"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general", server_default="general")
    data_type: Mapped[str] = mapped_column(String(50), nullable=False, default="string", server_default="string")
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    updated_by_user: Mapped[Optional[User]] = relationship("User", back_populates="updated_configs")


class User(Base):
    __tablename__ = "users"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(200), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("admin", "user", name="user_role"),
        nullable=False,
        default="user",
        server_default="user",
    )
    permission_group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("permission_groups.id"), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    position_id: Mapped[Optional[int]] = mapped_column(ForeignKey("positions.id"), nullable=True)
    sso_subject: Mapped[Optional[str]] = mapped_column(String(150), unique=True, nullable=True)
    auth_source: Mapped[str] = mapped_column(String(30), nullable=False, default="local", server_default="local")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    permission_group: Mapped[Optional[PermissionGroup]] = relationship("PermissionGroup", back_populates="users")
    department: Mapped[Optional[Department]] = relationship("Department", back_populates="users")
    position: Mapped[Optional[Position]] = relationship("Position", back_populates="users")
    documents: Mapped[list[Document]] = relationship("Document", back_populates="owner")
    summaries: Mapped[list[SummaryHistory]] = relationship(
        "SummaryHistory",
        back_populates="user",
        foreign_keys="SummaryHistory.user_id",
    )
    reviewed_summaries: Mapped[list[SummaryHistory]] = relationship(
        "SummaryHistory",
        back_populates="reviewer",
        foreign_keys="SummaryHistory.reviewed_by",
    )
    system_logs: Mapped[list[SystemLog]] = relationship("SystemLog", back_populates="user")
    api_keys: Mapped[list[APIKey]] = relationship("APIKey", back_populates="creator")
    updated_configs: Mapped[list[SystemConfig]] = relationship("SystemConfig", back_populates="updated_by_user")
    login_history_records: Mapped[list[LoginHistory]] = relationship("LoginHistory", back_populates="user")
    created_work_documents: Mapped[list[WorkAssignmentDocument]] = relationship(
        "WorkAssignmentDocument",
        back_populates="assigned_by_user",
    )
    assigned_work_items: Mapped[list[WorkItem]] = relationship("WorkItem", back_populates="assignee")
    posted_notice_documents: Mapped[list[NoticeDocument]] = relationship("NoticeDocument", back_populates="posted_by_user")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size_kb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="processing",
        server_default="processing",
    )
    chunks: Mapped[list[ChunkMetadata]] = relationship(
        "ChunkMetadata",
        back_populates="document",
    )
    summaries: Mapped[list[SummaryHistory]] = relationship(
        "SummaryHistory",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class ChunkMetadata(Base):
    __tablename__ = "chunk_metadata"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    chunk_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    faiss_index_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_preview: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)

    document: Mapped[Document] = relationship("Document", back_populates="chunks")


class SummaryHistory(Base):
    __tablename__ = "summary_history"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    summary_text: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)
    is_reviewed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    document: Mapped[Document] = relationship("Document", back_populates="summaries")
    user: Mapped[User] = relationship(
        "User",
        back_populates="summaries",
        foreign_keys=[user_id],
    )
    reviewer: Mapped[Optional[User]] = relationship(
        "User",
        back_populates="reviewed_summaries",
        foreign_keys=[reviewed_by],
    )


class WorkAssignmentDocument(Base):
    __tablename__ = "work_assignment_documents"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issuing_unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("issuing_units.id"), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    assigned_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    issuing_unit: Mapped[Optional[IssuingUnit]] = relationship("IssuingUnit", back_populates="work_assignment_documents")
    department: Mapped[Optional[Department]] = relationship(
        "Department",
        back_populates="work_assignment_documents",
        foreign_keys=[department_id],
    )
    assigned_department: Mapped[Optional[Department]] = relationship(
        "Department",
        back_populates="assigned_work_documents",
        foreign_keys=[assigned_department_id],
    )
    assigned_by_user: Mapped[Optional[User]] = relationship("User", back_populates="created_work_documents")
    work_items: Mapped[list[WorkItem]] = relationship("WorkItem", back_populates="work_document", cascade="all, delete-orphan")


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_document_id: Mapped[int] = mapped_column(ForeignKey("work_assignment_documents.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignee_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    position_id: Mapped[Optional[int]] = mapped_column(ForeignKey("positions.id"), nullable=True)
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="normal", server_default="normal")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    work_document: Mapped[WorkAssignmentDocument] = relationship("WorkAssignmentDocument", back_populates="work_items")
    assignee: Mapped[Optional[User]] = relationship("User", back_populates="assigned_work_items")
    department: Mapped[Optional[Department]] = relationship("Department", back_populates="work_items")
    position: Mapped[Optional[Position]] = relationship("Position", back_populates="work_items")


class NoticeDocument(Base):
    __tablename__ = "notice_documents"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notice_code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issuing_unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("issuing_units.id"), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    posted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    issuing_unit: Mapped[Optional[IssuingUnit]] = relationship("IssuingUnit", back_populates="notice_documents")
    department: Mapped[Optional[Department]] = relationship("Department", back_populates="notice_documents")
    posted_by_user: Mapped[Optional[User]] = relationship("User", back_populates="posted_notice_documents")


class SystemLog(Base):
    __tablename__ = "system_logs"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[Optional[User]] = relationship("User", back_populates="system_logs")


class APIKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    key_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        onupdate=func.now(),
    )

    creator: Mapped[User] = relationship("User", back_populates="api_keys")
