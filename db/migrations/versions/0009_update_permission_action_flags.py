"""update_permission_action_flags

Revision ID: 0009_update_permission_action_flags
Revises: 0008_action_function_mappings
Create Date: 2026-05-31 01:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_update_permission_action_flags"
down_revision = "0008_action_function_mappings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE permission_group_functions pgf "
            "SET "
            "  pgf.can_view = 1, "
            "  pgf.can_create = IF(EXISTS(SELECT 1 FROM action_function_mappings afm "
            "    WHERE afm.function_id = pgf.function_id AND afm.action_type = 'create' AND afm.is_active = 1), 1, 0), "
            "  pgf.can_update = IF(EXISTS(SELECT 1 FROM action_function_mappings afm "
            "    WHERE afm.function_id = pgf.function_id AND afm.action_type = 'update' AND afm.is_active = 1), 1, 0), "
            "  pgf.can_delete = IF(EXISTS(SELECT 1 FROM action_function_mappings afm "
            "    WHERE afm.function_id = pgf.function_id AND afm.action_type = 'delete' AND afm.is_active = 1), 1, 0)"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE permission_group_functions pgf "
            "SET pgf.can_create = 0, pgf.can_update = 0, pgf.can_delete = 0"
        )
    )
