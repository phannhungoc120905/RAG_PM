"""seed_permission_mapping

Revision ID: 0006_seed_permission_mapping
Revises: 0005_seed_org_defaults
Create Date: 2026-05-31 00:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_seed_permission_mapping"
down_revision = "0005_seed_org_defaults"
branch_labels = None
depends_on = None


SYSTEM_FUNCTIONS = [
    {"code": "QT-01", "name": "Quản lý cấu hình hệ thống", "module": "SYSTEM_FUNCTIONS"},
    {"code": "QT-02", "name": "Quản lý API Key", "module": "SYSTEM_FUNCTIONS"},
    {"code": "QT-03", "name": "Quản lý Nhóm quyền", "module": "SYSTEM_FUNCTIONS"},
    {"code": "QT-04", "name": "Quản lý danh mục Chức năng hệ thống", "module": "SYSTEM_FUNCTIONS"},
    {"code": "QT-05", "name": "Phân quyền người dùng", "module": "SYSTEM_FUNCTIONS"},
    {"code": "QT-06", "name": "Log API - Nhật ký truy cập hệ thống", "module": "SYSTEM_FUNCTIONS"},
    {"code": "QT-07", "name": "Nhật ký sử dụng hệ thống", "module": "SYSTEM_FUNCTIONS"},
    {"code": "QT-08", "name": "Sao lưu dữ liệu hệ thống", "module": "SYSTEM_FUNCTIONS"},
    {"code": "KT-01", "name": "Đăng nhập SSO nội bộ", "module": "SYSTEM_FUNCTIONS"},
    {"code": "KT-02", "name": "Nhật ký đăng nhập hệ thống", "module": "SYSTEM_FUNCTIONS"},
    {"code": "KT-03", "name": "Quản lý danh mục đơn vị ban hành", "module": "SYSTEM_FUNCTIONS"},
    {"code": "KT-04", "name": "Quản lý danh mục phòng ban và chức vụ", "module": "SYSTEM_FUNCTIONS"},
]

BUSINESS_FUNCTIONS = [
    {"code": "KT-05", "name": "Quản lý văn bản giao việc", "module": "BUSINESS_FUNCTIONS"},
    {"code": "KT-06", "name": "Quản lý danh sách việc", "module": "BUSINESS_FUNCTIONS"},
    {"code": "KT-07", "name": "Quản lý văn bản thông báo", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TX-01", "name": "Tải lên văn bản đa định dạng", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TX-02", "name": "Tích hợp OCR nhận diện chữ viết", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TX-03", "name": "Chuẩn hóa font tiếng Việt", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TX-04", "name": "Tự động làm sạch nhiễu hành chính", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TX-05", "name": "Nhận diện cấu trúc văn bản", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TX-06", "name": "Phân loại văn bản tự động", "module": "BUSINESS_FUNCTIONS"},
    {"code": "AI-05", "name": "Truy xuất ngữ cảnh thông minh", "module": "BUSINESS_FUNCTIONS"},
    {"code": "AI-07", "name": "Sinh tóm tắt tự động", "module": "BUSINESS_FUNCTIONS"},
    {"code": "AI-08", "name": "Cơ chế groundedness", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TT-01", "name": "Giao diện Split-view xem song song", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TT-02", "name": "Cuộn đồng bộ và nhảy trang", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TT-03", "name": "Trích dẫn nguồn chính xác", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TT-04", "name": "Quản lý lịch sử tóm tắt", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TT-05", "name": "Chỉnh sửa nội dung AI sinh", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TT-06", "name": "Đánh giá chất lượng bản tóm tắt", "module": "BUSINESS_FUNCTIONS"},
    {"code": "TT-07", "name": "Xuất bản dữ liệu tóm tắt", "module": "BUSINESS_FUNCTIONS"},
    {"code": "NC-01", "name": "Hỏi đáp tự do", "module": "BUSINESS_FUNCTIONS"},
    {"code": "NC-03", "name": "So sánh phiên bản văn bản", "module": "BUSINESS_FUNCTIONS"},
    {"code": "NC-04", "name": "Phân tích tác động điều khoản", "module": "BUSINESS_FUNCTIONS"},
    {"code": "BC-01", "name": "Tìm kiếm văn bản", "module": "BUSINESS_FUNCTIONS"},
    {"code": "BC-02", "name": "Dashboard thống kê", "module": "BUSINESS_FUNCTIONS"},
    {"code": "BC-03", "name": "Báo cáo lịch sử sử dụng hệ thống", "module": "BUSINESS_FUNCTIONS"},
    {"code": "BC-04", "name": "Thông báo trạng thái xử lý", "module": "BUSINESS_FUNCTIONS"},
    {"code": "BC-05", "name": "Xuất báo cáo tổng hợp", "module": "BUSINESS_FUNCTIONS"},
]

PERMISSION_GROUPS = [
    {"code": "ADMIN", "name": "Quản trị hệ thống", "description": "Admin"},
    {"code": "AGENCY_LEADER", "name": "Lãnh đạo cơ quan", "description": "Agency leader"},
    {"code": "DEPARTMENT_LEADER", "name": "Trưởng phòng", "description": "Department leader"},
    {"code": "STAFF", "name": "Chuyên viên/Cán bộ", "description": "Staff"},
]

GROUP_FUNCTION_MAPPING = {
    "ADMIN": [
        "QT-01", "QT-02", "QT-03", "QT-04", "QT-05", "QT-06", "QT-07", "QT-08",
        "KT-01", "KT-02", "KT-03", "KT-04", "KT-07",
        "BC-02",
    ],
    "AGENCY_LEADER": [
        "TT-01", "TT-02", "TT-03", "TT-04", "TT-05", "TT-06", "TT-07",
        "AI-05", "AI-07", "AI-08",
        "NC-01", "NC-03", "NC-04",
        "BC-01", "BC-02", "BC-03", "BC-04", "BC-05",
        "KT-05", "KT-06", "KT-07",
    ],
    "DEPARTMENT_LEADER": [
        "TT-01", "TT-02", "TT-03", "TT-04", "TT-05",
        "NC-01",
        "KT-05", "KT-06",
        "BC-03",
    ],
    "STAFF": [
        "TX-01", "TX-02", "TX-03", "TX-04", "TX-05", "TX-06",
        "AI-07",
        "TT-01", "TT-02", "TT-03",
        "KT-06",
        "BC-04",
    ],
}


def _insert_function_rows(connection: sa.engine.Connection) -> None:
    all_functions = SYSTEM_FUNCTIONS + BUSINESS_FUNCTIONS
    for item in all_functions:
        exists = connection.execute(
            sa.text("SELECT 1 FROM system_functions WHERE code = :code"),
            {"code": item["code"]},
        ).fetchone()
        if not exists:
            connection.execute(
                sa.text(
                    "INSERT INTO system_functions (name, code, module, description, is_active) "
                    "VALUES (:name, :code, :module, :description, 1)"
                ),
                {
                    "name": item["name"],
                    "code": item["code"],
                    "module": item["module"],
                    "description": item.get("description"),
                },
            )


def _insert_group_rows(connection: sa.engine.Connection) -> None:
    for item in PERMISSION_GROUPS:
        exists = connection.execute(
            sa.text("SELECT 1 FROM permission_groups WHERE code = :code"),
            {"code": item["code"]},
        ).fetchone()
        if not exists:
            connection.execute(
                sa.text(
                    "INSERT INTO permission_groups (name, code, description, is_active) "
                    "VALUES (:name, :code, :description, 1)"
                ),
                item,
            )


def _get_id_by_code(connection: sa.engine.Connection, table: str, code: str) -> int:
    row = connection.execute(
        sa.text(f"SELECT id FROM {table} WHERE code = :code"),
        {"code": code},
    ).fetchone()
    if not row:
        raise ValueError(f"Missing {table} record for code={code}")
    return int(row[0])


def _insert_group_permissions(connection: sa.engine.Connection) -> None:
    for group_code, function_codes in GROUP_FUNCTION_MAPPING.items():
        group_id = _get_id_by_code(connection, "permission_groups", group_code)
        for function_code in function_codes:
            function_id = _get_id_by_code(connection, "system_functions", function_code)
            exists = connection.execute(
                sa.text(
                    "SELECT 1 FROM permission_group_functions "
                    "WHERE group_id = :group_id AND function_id = :function_id"
                ),
                {"group_id": group_id, "function_id": function_id},
            ).fetchone()
            if not exists:
                connection.execute(
                    sa.text(
                        "INSERT INTO permission_group_functions "
                        "(group_id, function_id, can_view, can_create, can_update, can_delete) "
                        "VALUES (:group_id, :function_id, 1, 0, 0, 0)"
                    ),
                    {"group_id": group_id, "function_id": function_id},
                )


def upgrade() -> None:
    connection = op.get_bind()
    _insert_function_rows(connection)
    _insert_group_rows(connection)
    _insert_group_permissions(connection)


def downgrade() -> None:
    connection = op.get_bind()
    group_codes = [item["code"] for item in PERMISSION_GROUPS]
    function_codes = [item["code"] for item in SYSTEM_FUNCTIONS + BUSINESS_FUNCTIONS]

    group_ids = connection.execute(
        sa.text("SELECT id FROM permission_groups WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": group_codes},
    ).fetchall()
    function_ids = connection.execute(
        sa.text("SELECT id FROM system_functions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": function_codes},
    ).fetchall()

    if group_ids and function_ids:
        connection.execute(
            sa.text(
                "DELETE FROM permission_group_functions "
                "WHERE group_id IN :group_ids AND function_id IN :function_ids"
            ).bindparams(
                sa.bindparam("group_ids", expanding=True),
                sa.bindparam("function_ids", expanding=True),
            ),
            {
                "group_ids": [row[0] for row in group_ids],
                "function_ids": [row[0] for row in function_ids],
            },
        )

    connection.execute(
        sa.text("DELETE FROM permission_groups WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": group_codes},
    )
    connection.execute(
        sa.text("DELETE FROM system_functions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": function_codes},
    )
