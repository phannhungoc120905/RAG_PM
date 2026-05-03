"""admin_management_features

Revision ID: 0002_admin_management_features
Revises: 0001_initial_schema
Create Date: 2026-05-03 23:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_admin_management_features"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permission_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "system_functions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "permission_group_functions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("function_id", sa.Integer(), nullable=False),
        sa.Column("can_view", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("can_create", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("can_update", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("can_delete", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["function_id"], ["system_functions.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["permission_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "system_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("config_key", sa.String(length=100), nullable=False),
        sa.Column("config_value", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False, server_default="general"),
        sa.Column("data_type", sa.String(length=50), nullable=False, server_default="string"),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("config_key"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.add_column("users", sa.Column("permission_group_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_permission_group_id",
        "users",
        "permission_groups",
        ["permission_group_id"],
        ["id"],
    )

    op.add_column("api_keys", sa.Column("description", sa.String(length=255), nullable=True))
    op.add_column("api_keys", sa.Column("updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "updated_at")
    op.drop_column("api_keys", "description")

    op.drop_constraint("fk_users_permission_group_id", "users", type_="foreignkey")
    op.drop_column("users", "permission_group_id")

    op.drop_table("system_configs")
    op.drop_table("permission_group_functions")
    op.drop_table("system_functions")
    op.drop_table("permission_groups")
