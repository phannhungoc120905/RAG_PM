"""position_permission_groups

Revision ID: 0007_position_permission_groups
Revises: 0006_seed_permission_mapping
Create Date: 2026-05-31 00:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_position_permission_groups"
down_revision = "0006_seed_permission_mapping"
branch_labels = None
depends_on = None


POSITION_GROUP_MAPPING = [
    {"position_code": "AGENCY_LEADER", "group_code": "AGENCY_LEADER"},
    {"position_code": "DEPARTMENT_LEADER", "group_code": "DEPARTMENT_LEADER"},
    {"position_code": "STAFF", "group_code": "STAFF"},
]


def _get_id_by_code(connection: sa.engine.Connection, table: str, code: str) -> int | None:
    row = connection.execute(
        sa.text(f"SELECT id FROM {table} WHERE code = :code"),
        {"code": code},
    ).fetchone()
    if not row:
        return None
    return int(row[0])


def upgrade() -> None:
    op.create_table(
        "position_permission_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("position_id", sa.Integer(), nullable=False),
        sa.Column("permission_group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.ForeignKeyConstraint(["permission_group_id"], ["permission_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("position_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    connection = op.get_bind()
    for item in POSITION_GROUP_MAPPING:
        position_id = _get_id_by_code(connection, "positions", item["position_code"])
        group_id = _get_id_by_code(connection, "permission_groups", item["group_code"])
        if not position_id or not group_id:
            continue
        exists = connection.execute(
            sa.text(
                "SELECT 1 FROM position_permission_groups "
                "WHERE position_id = :position_id"
            ),
            {"position_id": position_id},
        ).fetchone()
        if not exists:
            connection.execute(
                sa.text(
                    "INSERT INTO position_permission_groups "
                    "(position_id, permission_group_id) "
                    "VALUES (:position_id, :permission_group_id)"
                ),
                {"position_id": position_id, "permission_group_id": group_id},
            )


def downgrade() -> None:
    op.drop_table("position_permission_groups")
