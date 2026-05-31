"""seed_org_defaults

Revision ID: 0005_seed_org_defaults
Revises: 0004_compact_ai_document_fields
Create Date: 2026-05-31 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_seed_org_defaults"
down_revision = "0004_compact_ai_document_fields"
branch_labels = None
depends_on = None


POSITIONS = [
    {"code": "AGENCY_LEADER", "name": "Lãnh đạo cơ quan"},
    {"code": "DEPARTMENT_LEADER", "name": "Trưởng phòng"},
    {"code": "STAFF", "name": "Chuyên viên/Cán bộ"},
]

DEPARTMENTS = [
    {"code": "ADMIN", "name": "Hành chính"},
    {"code": "FINANCE", "name": "Tài chính"},
    {"code": "HR", "name": "Nhân sự"},
    {"code": "IT", "name": "Công nghệ thông tin"},
]


def _insert_if_missing(table_name: str, rows: list[dict[str, str]]) -> None:
    connection = op.get_bind()
    for row in rows:
        exists = connection.execute(
            sa.text(f"SELECT 1 FROM {table_name} WHERE code = :code"),
            {"code": row["code"]},
        ).fetchone()
        if not exists:
            connection.execute(
                sa.text(
                    f"INSERT INTO {table_name} (code, name, is_active) "
                    "VALUES (:code, :name, 1)"
                ),
                {"code": row["code"], "name": row["name"]},
            )


def upgrade() -> None:
    _insert_if_missing("positions", POSITIONS)
    _insert_if_missing("departments", DEPARTMENTS)


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM positions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": [item["code"] for item in POSITIONS]},
    )
    connection.execute(
        sa.text("DELETE FROM departments WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": [item["code"] for item in DEPARTMENTS]},
    )
