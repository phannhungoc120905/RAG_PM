"""compact_ai_document_fields

Revision ID: 0004_compact_ai_document_fields
Revises: 0003_legacy_management_features
Create Date: 2026-05-06 10:25:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0004_compact_ai_document_fields"
down_revision = "0003_legacy_management_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # documents: keep one table as the center for file metadata, OCR output,
    # structure extraction, page index, review state, and processing lifecycle.
    op.add_column("documents", sa.Column("document_type", sa.String(length=100), nullable=True))
    op.add_column("documents", sa.Column("document_number", sa.String(length=150), nullable=True))
    op.add_column("documents", sa.Column("document_title", sa.String(length=500), nullable=True))
    op.add_column("documents", sa.Column("document_summary", mysql.LONGTEXT(), nullable=True))
    op.add_column("documents", sa.Column("issuer_name", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("issued_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("effective_date", sa.Date(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("language", sa.String(length=20), nullable=True, server_default="vi"),
    )
    op.add_column("documents", sa.Column("source_format", sa.String(length=20), nullable=True))
    op.add_column("documents", sa.Column("mime_type", sa.String(length=100), nullable=True))
    op.add_column(
        "documents",
        sa.Column("page_count", sa.Integer(), nullable=True, server_default=sa.text("0")),
    )
    op.add_column("documents", sa.Column("ocr_text", mysql.LONGTEXT(), nullable=True))
    op.add_column("documents", sa.Column("clean_text", mysql.LONGTEXT(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("processing_status", sa.String(length=50), nullable=False, server_default="uploaded"),
    )
    op.add_column("documents", sa.Column("processing_error", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("classification_label", sa.String(length=100), nullable=True))
    op.add_column("documents", sa.Column("classification_score", sa.Numeric(5, 4), nullable=True))
    op.add_column("documents", sa.Column("structure_json", mysql.LONGTEXT(), nullable=True))
    op.add_column("documents", sa.Column("page_index_json", mysql.LONGTEXT(), nullable=True))
    op.add_column("documents", sa.Column("storage_meta_json", mysql.LONGTEXT(), nullable=True))
    op.add_column("documents", sa.Column("uploaded_by", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("processed_by", sa.Integer(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="pending"),
    )
    op.add_column("documents", sa.Column("reviewed_by", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("documents", sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.create_foreign_key("fk_documents_uploaded_by", "documents", "users", ["uploaded_by"], ["id"])
    op.create_foreign_key("fk_documents_processed_by", "documents", "users", ["processed_by"], ["id"])
    op.create_foreign_key("fk_documents_reviewed_by", "documents", "users", ["reviewed_by"], ["id"])

    op.create_index("idx_documents_processing_status", "documents", ["processing_status"])
    op.create_index("idx_documents_document_number", "documents", ["document_number"])
    op.create_index("idx_documents_document_type", "documents", ["document_type"])
    op.create_index("idx_documents_issued_date", "documents", ["issued_date"])
    op.create_index("idx_documents_deleted_at", "documents", ["deleted_at"])

    # chunk_metadata: expand the existing table instead of creating separate
    # section/citation/vector mapping tables.
    op.add_column("chunk_metadata", sa.Column("chunk_type", sa.String(length=50), nullable=True))
    op.add_column("chunk_metadata", sa.Column("section_type", sa.String(length=50), nullable=True))
    op.add_column("chunk_metadata", sa.Column("section_code", sa.String(length=100), nullable=True))
    op.add_column("chunk_metadata", sa.Column("section_title", sa.String(length=500), nullable=True))
    op.add_column("chunk_metadata", sa.Column("end_line", sa.Integer(), nullable=True))
    op.add_column("chunk_metadata", sa.Column("end_page", sa.Integer(), nullable=True))
    op.add_column("chunk_metadata", sa.Column("token_count", sa.Integer(), nullable=True))
    op.add_column(
        "chunk_metadata",
        sa.Column("embedding_status", sa.String(length=30), nullable=False, server_default="pending"),
    )
    op.add_column("chunk_metadata", sa.Column("embedding_model", sa.String(length=100), nullable=True))
    op.add_column("chunk_metadata", sa.Column("bm25_text", mysql.LONGTEXT(), nullable=True))
    op.add_column("chunk_metadata", sa.Column("citation_json", mysql.LONGTEXT(), nullable=True))
    op.add_column("chunk_metadata", sa.Column("chunk_hash", sa.String(length=128), nullable=True))
    op.add_column("chunk_metadata", sa.Column("metadata_json", mysql.LONGTEXT(), nullable=True))
    op.add_column(
        "chunk_metadata",
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("idx_chunk_document_id", "chunk_metadata", ["document_id"])
    op.create_index("idx_chunk_section_code", "chunk_metadata", ["section_code"])
    op.create_index("idx_chunk_page_number", "chunk_metadata", ["page_number"])

    # summary_history: versioning, source traceability, groundedness and review
    # all live in the same table to avoid more summary tables.
    op.add_column(
        "summary_history",
        sa.Column("summary_type", sa.String(length=30), nullable=False, server_default="summary"),
    )
    op.add_column(
        "summary_history",
        sa.Column("version_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column("summary_history", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("summary_history", sa.Column("prompt_template", sa.String(length=100), nullable=True))
    op.add_column("summary_history", sa.Column("model_name", sa.String(length=100), nullable=True))
    op.add_column("summary_history", sa.Column("source_chunk_ids_json", mysql.LONGTEXT(), nullable=True))
    op.add_column("summary_history", sa.Column("groundedness_score", sa.Numeric(5, 4), nullable=True))
    op.add_column(
        "summary_history",
        sa.Column("hallucination_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("summary_history", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column("summary_history", sa.Column("feedback_score", sa.Integer(), nullable=True))
    op.add_column("summary_history", sa.Column("feedback_comment", sa.Text(), nullable=True))
    op.add_column("summary_history", sa.Column("exported_formats_json", mysql.LONGTEXT(), nullable=True))
    op.add_column(
        "summary_history",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )

    op.create_index("idx_summary_document_id", "summary_history", ["document_id"])
    op.create_index("idx_summary_user_id", "summary_history", ["user_id"])
    op.create_index("idx_summary_reviewed", "summary_history", ["is_reviewed"])
    op.create_index("idx_summary_version_no", "summary_history", ["version_no"])

    # system_logs: reuse one table for API logs, usage logs, audit logs and
    # AI processing logs.
    op.add_column("system_logs", sa.Column("module_name", sa.String(length=100), nullable=True))
    op.add_column("system_logs", sa.Column("entity_type", sa.String(length=100), nullable=True))
    op.add_column("system_logs", sa.Column("entity_id", sa.Integer(), nullable=True))
    op.add_column(
        "system_logs",
        sa.Column("log_type", sa.String(length=30), nullable=False, server_default="system"),
    )
    op.add_column("system_logs", sa.Column("request_id", sa.String(length=100), nullable=True))
    op.add_column("system_logs", sa.Column("username_snapshot", sa.String(length=100), nullable=True))

    op.create_index("idx_system_logs_log_type", "system_logs", ["log_type"])
    op.create_index("idx_system_logs_module_name", "system_logs", ["module_name"])
    op.create_index("idx_system_logs_entity_type_entity_id", "system_logs", ["entity_type", "entity_id"])
    op.create_index("idx_system_logs_created_at", "system_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_system_logs_created_at", table_name="system_logs")
    op.drop_index("idx_system_logs_entity_type_entity_id", table_name="system_logs")
    op.drop_index("idx_system_logs_module_name", table_name="system_logs")
    op.drop_index("idx_system_logs_log_type", table_name="system_logs")
    op.drop_column("system_logs", "username_snapshot")
    op.drop_column("system_logs", "request_id")
    op.drop_column("system_logs", "log_type")
    op.drop_column("system_logs", "entity_id")
    op.drop_column("system_logs", "entity_type")
    op.drop_column("system_logs", "module_name")

    op.drop_index("idx_summary_version_no", table_name="summary_history")
    op.drop_index("idx_summary_reviewed", table_name="summary_history")
    op.drop_index("idx_summary_user_id", table_name="summary_history")
    op.drop_index("idx_summary_document_id", table_name="summary_history")
    op.drop_column("summary_history", "is_deleted")
    op.drop_column("summary_history", "exported_formats_json")
    op.drop_column("summary_history", "feedback_comment")
    op.drop_column("summary_history", "feedback_score")
    op.drop_column("summary_history", "review_note")
    op.drop_column("summary_history", "hallucination_flag")
    op.drop_column("summary_history", "groundedness_score")
    op.drop_column("summary_history", "source_chunk_ids_json")
    op.drop_column("summary_history", "model_name")
    op.drop_column("summary_history", "prompt_template")
    op.drop_column("summary_history", "title")
    op.drop_column("summary_history", "version_no")
    op.drop_column("summary_history", "summary_type")

    op.drop_index("idx_chunk_page_number", table_name="chunk_metadata")
    op.drop_index("idx_chunk_section_code", table_name="chunk_metadata")
    op.drop_index("idx_chunk_document_id", table_name="chunk_metadata")
    op.drop_column("chunk_metadata", "created_at")
    op.drop_column("chunk_metadata", "metadata_json")
    op.drop_column("chunk_metadata", "chunk_hash")
    op.drop_column("chunk_metadata", "citation_json")
    op.drop_column("chunk_metadata", "bm25_text")
    op.drop_column("chunk_metadata", "embedding_model")
    op.drop_column("chunk_metadata", "embedding_status")
    op.drop_column("chunk_metadata", "token_count")
    op.drop_column("chunk_metadata", "end_page")
    op.drop_column("chunk_metadata", "end_line")
    op.drop_column("chunk_metadata", "section_title")
    op.drop_column("chunk_metadata", "section_code")
    op.drop_column("chunk_metadata", "section_type")
    op.drop_column("chunk_metadata", "chunk_type")

    op.drop_index("idx_documents_deleted_at", table_name="documents")
    op.drop_index("idx_documents_issued_date", table_name="documents")
    op.drop_index("idx_documents_document_type", table_name="documents")
    op.drop_index("idx_documents_document_number", table_name="documents")
    op.drop_index("idx_documents_processing_status", table_name="documents")
    op.drop_constraint("fk_documents_reviewed_by", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_processed_by", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_uploaded_by", "documents", type_="foreignkey")
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "reviewed_at")
    op.drop_column("documents", "reviewed_by")
    op.drop_column("documents", "review_status")
    op.drop_column("documents", "processed_by")
    op.drop_column("documents", "uploaded_by")
    op.drop_column("documents", "storage_meta_json")
    op.drop_column("documents", "page_index_json")
    op.drop_column("documents", "structure_json")
    op.drop_column("documents", "classification_score")
    op.drop_column("documents", "classification_label")
    op.drop_column("documents", "processing_error")
    op.drop_column("documents", "processing_status")
    op.drop_column("documents", "clean_text")
    op.drop_column("documents", "ocr_text")
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "mime_type")
    op.drop_column("documents", "source_format")
    op.drop_column("documents", "language")
    op.drop_column("documents", "effective_date")
    op.drop_column("documents", "issued_date")
    op.drop_column("documents", "issuer_name")
    op.drop_column("documents", "document_summary")
    op.drop_column("documents", "document_title")
    op.drop_column("documents", "document_number")
    op.drop_column("documents", "document_type")
