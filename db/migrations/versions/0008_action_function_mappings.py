"""action_function_mappings

Revision ID: 0008_action_function_mappings
Revises: 0007_position_permission_groups
Create Date: 2026-05-31 00:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_action_function_mappings"
down_revision = "0007_position_permission_groups"
branch_labels = None
depends_on = None


ACTION_MAPPINGS = [
    # System configs
    {"action_key": "admin.system.configs.list", "function_code": "QT-01", "action_type": "view"},
    {"action_key": "admin.system.configs.create", "function_code": "QT-01", "action_type": "create"},
    {"action_key": "admin.system.configs.update", "function_code": "QT-01", "action_type": "update"},
    {"action_key": "admin.system.configs.delete", "function_code": "QT-01", "action_type": "delete"},
    {"action_key": "admin.system.status.view", "function_code": "QT-01", "action_type": "view"},
    {"action_key": "admin.system.app_config.view", "function_code": "QT-01", "action_type": "view"},
    {"action_key": "admin.system.app_config.update", "function_code": "QT-01", "action_type": "update"},

    # Security
    {"action_key": "admin.security.api_keys.list", "function_code": "QT-02", "action_type": "view"},
    {"action_key": "admin.security.api_keys.create", "function_code": "QT-02", "action_type": "create"},
    {"action_key": "admin.security.api_keys.update", "function_code": "QT-02", "action_type": "update"},
    {"action_key": "admin.security.api_keys.delete", "function_code": "QT-02", "action_type": "delete"},
    {"action_key": "admin.security.permission_groups.list", "function_code": "QT-03", "action_type": "view"},
    {"action_key": "admin.security.permission_groups.create", "function_code": "QT-03", "action_type": "create"},
    {"action_key": "admin.security.permission_groups.update", "function_code": "QT-03", "action_type": "update"},
    {"action_key": "admin.security.permission_groups.delete", "function_code": "QT-03", "action_type": "delete"},
    {"action_key": "admin.security.system_functions.list", "function_code": "QT-04", "action_type": "view"},
    {"action_key": "admin.security.system_functions.create", "function_code": "QT-04", "action_type": "create"},
    {"action_key": "admin.security.system_functions.update", "function_code": "QT-04", "action_type": "update"},
    {"action_key": "admin.security.system_functions.delete", "function_code": "QT-04", "action_type": "delete"},

    # Logs & backups
    {"action_key": "admin.logs.list", "function_code": "QT-06", "action_type": "view"},
    {"action_key": "admin.logs.export", "function_code": "QT-07", "action_type": "view"},
    {"action_key": "admin.login_history.list", "function_code": "KT-02", "action_type": "view"},
    {"action_key": "admin.backups.list", "function_code": "QT-08", "action_type": "view"},
    {"action_key": "admin.backups.create", "function_code": "QT-08", "action_type": "create"},
    {"action_key": "admin.backups.restore", "function_code": "QT-08", "action_type": "update"},

    # Entities
    {"action_key": "admin.entities.issuing_units.list", "function_code": "KT-03", "action_type": "view"},
    {"action_key": "admin.entities.issuing_units.create", "function_code": "KT-03", "action_type": "create"},
    {"action_key": "admin.entities.issuing_units.update", "function_code": "KT-03", "action_type": "update"},
    {"action_key": "admin.entities.issuing_units.delete", "function_code": "KT-03", "action_type": "delete"},
    {"action_key": "admin.entities.departments.list", "function_code": "KT-04", "action_type": "view"},
    {"action_key": "admin.entities.departments.create", "function_code": "KT-04", "action_type": "create"},
    {"action_key": "admin.entities.departments.update", "function_code": "KT-04", "action_type": "update"},
    {"action_key": "admin.entities.departments.delete", "function_code": "KT-04", "action_type": "delete"},
    {"action_key": "admin.entities.positions.list", "function_code": "KT-04", "action_type": "view"},
    {"action_key": "admin.entities.positions.create", "function_code": "KT-04", "action_type": "create"},
    {"action_key": "admin.entities.positions.update", "function_code": "KT-04", "action_type": "update"},
    {"action_key": "admin.entities.positions.delete", "function_code": "KT-04", "action_type": "delete"},

    # Work & notice
    {"action_key": "admin.work.documents.list", "function_code": "KT-05", "action_type": "view"},
    {"action_key": "admin.work.documents.create", "function_code": "KT-05", "action_type": "create"},
    {"action_key": "admin.work.documents.update", "function_code": "KT-05", "action_type": "update"},
    {"action_key": "admin.work.documents.delete", "function_code": "KT-05", "action_type": "delete"},
    {"action_key": "admin.work.items.list", "function_code": "KT-06", "action_type": "view"},
    {"action_key": "admin.work.items.create", "function_code": "KT-06", "action_type": "create"},
    {"action_key": "admin.work.items.update", "function_code": "KT-06", "action_type": "update"},
    {"action_key": "admin.work.items.delete", "function_code": "KT-06", "action_type": "delete"},
    {"action_key": "admin.notice.documents.list", "function_code": "KT-07", "action_type": "view"},
    {"action_key": "admin.notice.documents.create", "function_code": "KT-07", "action_type": "create"},
    {"action_key": "admin.notice.documents.delete", "function_code": "KT-07", "action_type": "delete"},

    # API
    {"action_key": "api.supported_formats.view", "function_code": "TX-01", "action_type": "view"},
    {"action_key": "api.ollama_health.view", "function_code": "AI-05", "action_type": "view"},
    {"action_key": "api.upload.create", "function_code": "TX-01", "action_type": "create"},
    {"action_key": "api.documents.list", "function_code": "BC-01", "action_type": "view"},
    {"action_key": "api.documents.detail", "function_code": "BC-01", "action_type": "view"},
    {"action_key": "api.documents.delete", "function_code": "TT-08", "action_type": "delete"},
    {"action_key": "api.summaries.create", "function_code": "AI-07", "action_type": "create"},
    {"action_key": "api.summaries.create", "function_code": "NC-01", "action_type": "create"},
    {"action_key": "api.search.create", "function_code": "AI-05", "action_type": "create"},
    {"action_key": "api.history.list", "function_code": "TT-04", "action_type": "view"},
    {"action_key": "api.summaries.detail", "function_code": "TT-01", "action_type": "view"},
    {"action_key": "api.summaries.review", "function_code": "TT-05", "action_type": "update"},
    {"action_key": "api.summaries.feedback", "function_code": "TT-06", "action_type": "create"},
    {"action_key": "api.summaries.export", "function_code": "TT-07", "action_type": "view"},

    # OCR
    {"action_key": "ocr.supported_formats.view", "function_code": "TX-02", "action_type": "view"},
    {"action_key": "ocr.extract_text.create", "function_code": "TX-02", "action_type": "create"},
    {"action_key": "ocr.analyze.create", "function_code": "TX-05", "action_type": "create"},
    {"action_key": "ocr.analyze_text.create", "function_code": "TX-05", "action_type": "create"},
    {"action_key": "ocr.upload_process.create", "function_code": "TX-02", "action_type": "create"},
    {"action_key": "ocr.search.create", "function_code": "AI-05", "action_type": "create"},
    {"action_key": "ocr.summarize.create", "function_code": "NC-01", "action_type": "create"},
]


TT_08_FUNCTION = {
    "code": "TT-08",
    "name": "Xoa van ban va du lieu lien quan",
    "module": "BUSINESS_FUNCTIONS",
}


def _get_id_by_code(connection: sa.engine.Connection, table: str, code: str) -> int | None:
    row = connection.execute(
        sa.text(f"SELECT id FROM {table} WHERE code = :code"),
        {"code": code},
    ).fetchone()
    if not row:
        return None
    return int(row[0])


def _ensure_function(connection: sa.engine.Connection, function: dict[str, str]) -> int | None:
    function_id = _get_id_by_code(connection, "system_functions", function["code"])
    if function_id:
        return function_id
    connection.execute(
        sa.text(
            "INSERT INTO system_functions (name, code, module, description, is_active) "
            "VALUES (:name, :code, :module, NULL, 1)"
        ),
        function,
    )
    return _get_id_by_code(connection, "system_functions", function["code"])


def _ensure_group_permission(
    connection: sa.engine.Connection,
    group_code: str,
    function_id: int,
) -> None:
    group_id = _get_id_by_code(connection, "permission_groups", group_code)
    if not group_id:
        return
    exists = connection.execute(
        sa.text(
            "SELECT 1 FROM permission_group_functions "
            "WHERE group_id = :group_id AND function_id = :function_id"
        ),
        {"group_id": group_id, "function_id": function_id},
    ).fetchone()
    if exists:
        return
    connection.execute(
        sa.text(
            "INSERT INTO permission_group_functions "
            "(group_id, function_id, can_view, can_create, can_update, can_delete) "
            "VALUES (:group_id, :function_id, 1, 0, 1, 1)"
        ),
        {"group_id": group_id, "function_id": function_id},
    )


def upgrade() -> None:
    op.create_table(
        "action_function_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action_key", sa.String(length=150), nullable=False),
        sa.Column("function_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=20), nullable=False, server_default="view"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["function_id"], ["system_functions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_key", "function_id", "action_type"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    connection = op.get_bind()
    tt08_id = _ensure_function(connection, TT_08_FUNCTION)
    if tt08_id:
        _ensure_group_permission(connection, "AGENCY_LEADER", tt08_id)

    for item in ACTION_MAPPINGS:
        function_id = _get_id_by_code(connection, "system_functions", item["function_code"])
        if not function_id:
            continue
        exists = connection.execute(
            sa.text(
                "SELECT 1 FROM action_function_mappings "
                "WHERE action_key = :action_key AND function_id = :function_id AND action_type = :action_type"
            ),
            {
                "action_key": item["action_key"],
                "function_id": function_id,
                "action_type": item["action_type"],
            },
        ).fetchone()
        if not exists:
            connection.execute(
                sa.text(
                    "INSERT INTO action_function_mappings "
                    "(action_key, function_id, action_type, is_active) "
                    "VALUES (:action_key, :function_id, :action_type, 1)"
                ),
                {
                    "action_key": item["action_key"],
                    "function_id": function_id,
                    "action_type": item["action_type"],
                },
            )


def downgrade() -> None:
    op.drop_table("action_function_mappings")
