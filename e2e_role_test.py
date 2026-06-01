from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import select

from db.database import SessionLocal
from db.models import Department, Position


BASE_URL = "http://127.0.0.1:8001"
AGENCY_USERNAME = "tphuongtran05"
AGENCY_PASSWORD = "Phuong.."
TEST_PASSWORD = "Test@123456"


def request(method: str, path: str, token: str | None = None, payload: dict | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return {
                "status": resp.status,
                "body": json.loads(raw) if raw else None,
                "raw": raw,
            }
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
        return {"status": exc.code, "body": body, "raw": raw}
    except URLError as exc:
        return {"status": 0, "body": str(exc), "raw": str(exc)}


def login(username: str, password: str) -> tuple[str | None, dict]:
    result = request("POST", "/auth/login", payload={"username": username, "password": password})
    token = result["body"].get("access_token") if result["status"] == 200 else None
    return token, result


def lookup_seed_ids() -> dict[str, int]:
    with SessionLocal() as db:
        department = db.scalar(select(Department).where(Department.code == "IT"))
        leader_position = db.scalar(select(Position).where(Position.code == "DEPARTMENT_LEADER"))
        staff_position = db.scalar(select(Position).where(Position.code == "STAFF"))
        if not department or not leader_position or not staff_position:
            raise RuntimeError("Missing seeded IT department or DEPARTMENT_LEADER/STAFF positions")
        return {
            "department_id": department.id,
            "department_code": department.code,
            "leader_position_id": leader_position.id,
            "staff_position_id": staff_position.id,
        }


def record(results: list[dict], role: str, name: str, method: str, path: str, actual: dict, expected: int | None = None) -> None:
    status = actual["status"]
    ok = expected is None or status == expected
    results.append(
        {
            "role": role,
            "name": name,
            "method": method,
            "path": path,
            "expected": expected,
            "status": status,
            "ok": ok,
            "body": sanitize_body(actual["body"]),
        }
    )


def sanitize_body(body):
    if isinstance(body, dict):
        sanitized = {key: sanitize_body(value) for key, value in body.items()}
        if "access_token" in sanitized:
            sanitized["access_token"] = "<redacted>"
        return sanitized
    if isinstance(body, list):
        return [sanitize_body(item) for item in body]
    return body


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    ids = lookup_seed_ids()
    results: list[dict] = []

    agency_token, agency_login = login(AGENCY_USERNAME, AGENCY_PASSWORD)
    record(results, "AGENCY_LEADER", "login", "POST", "/auth/login", agency_login, 200)
    if not agency_token:
        write_results(stamp, ids, {}, results)
        return 1

    leader_payload = {
        "username": f"dept_leader_e2e_{stamp}",
        "email": f"dept_leader_e2e_{stamp}@example.local",
        "password": TEST_PASSWORD,
        "department_id": ids["department_id"],
        "position_id": ids["leader_position_id"],
        "is_active": True,
    }
    staff_payload = {
        "username": f"staff_e2e_{stamp}",
        "email": f"staff_e2e_{stamp}@example.local",
        "password": TEST_PASSWORD,
        "department_id": ids["department_id"],
        "position_id": ids["staff_position_id"],
        "is_active": True,
    }

    created_leader = request("POST", "/admin/users", agency_token, leader_payload)
    created_staff = request("POST", "/admin/users", agency_token, staff_payload)
    record(results, "AGENCY_LEADER", "create department leader", "POST", "/admin/users", created_leader, 200)
    record(results, "AGENCY_LEADER", "create staff", "POST", "/admin/users", created_staff, 200)
    if created_leader["status"] != 200 or created_staff["status"] != 200:
        write_results(stamp, ids, {"leader": leader_payload, "staff": staff_payload}, results)
        return 1

    leader_id = created_leader["body"]["id"]
    staff_id = created_staff["body"]["id"]
    leader_token, leader_login = login(leader_payload["username"], TEST_PASSWORD)
    staff_token, staff_login = login(staff_payload["username"], TEST_PASSWORD)
    record(results, "DEPARTMENT_LEADER", "login", "POST", "/auth/login", leader_login, 200)
    record(results, "STAFF", "login", "POST", "/auth/login", staff_login, 200)
    if not leader_token or not staff_token:
        write_results(stamp, ids, {"leader": leader_payload, "staff": staff_payload}, results)
        return 1

    doc_payload = {
        "document_code": f"E2E-DOC-{stamp}",
        "title": "E2E work document",
        "content_summary": "Created by role e2e test",
        "department_id": ids["department_id"],
        "assigned_by_user_id": leader_id,
        "assigned_department_id": ids["department_id"],
        "due_date": "2026-06-30",
        "status": "assigned",
    }

    leader_doc_list = request("GET", "/admin/work-documents", leader_token)
    created_doc = request("POST", "/admin/work-documents", leader_token, doc_payload)
    record(results, "DEPARTMENT_LEADER", "list work documents", "GET", "/admin/work-documents", leader_doc_list, 200)
    record(results, "DEPARTMENT_LEADER", "create work document", "POST", "/admin/work-documents", created_doc, 200)
    doc_id = created_doc["body"]["id"] if created_doc["status"] == 200 else None

    item_id = None
    if doc_id:
        update_doc = request("PUT", f"/admin/work-documents/{doc_id}", leader_token, {"status": "in_progress"})
        record(results, "DEPARTMENT_LEADER", "update work document", "PUT", f"/admin/work-documents/{doc_id}", update_doc, 200)
        item_payload = {
            "work_document_id": doc_id,
            "title": "E2E assigned staff task",
            "description": "Task visible to staff",
            "assignee_user_id": staff_id,
            "department_id": ids["department_id"],
            "position_id": ids["staff_position_id"],
            "priority": "normal",
            "status": "pending",
            "due_date": "2026-06-25",
        }
        leader_item_list = request("GET", "/admin/work-items", leader_token)
        created_item = request("POST", "/admin/work-items", leader_token, item_payload)
        record(results, "DEPARTMENT_LEADER", "list work items", "GET", "/admin/work-items", leader_item_list, 200)
        record(results, "DEPARTMENT_LEADER", "create work item", "POST", "/admin/work-items", created_item, 200)
        item_id = created_item["body"]["id"] if created_item["status"] == 200 else None

        delete_item_payload = dict(item_payload)
        delete_item_payload["title"] = "E2E temporary task for delete"
        temp_item = request("POST", "/admin/work-items", leader_token, delete_item_payload)
        record(results, "DEPARTMENT_LEADER", "create temp work item", "POST", "/admin/work-items", temp_item, 200)
        if temp_item["status"] == 200:
            temp_id = temp_item["body"]["id"]
            deleted_temp = request("DELETE", f"/admin/work-items/{temp_id}", leader_token)
            record(results, "DEPARTMENT_LEADER", "delete work item", "DELETE", f"/admin/work-items/{temp_id}", deleted_temp, 200)

    leader_checks = [
        ("me", "GET", "/auth/me", 200, None),
        ("cannot manage users", "GET", "/admin/users", 403, None),
        ("history allowed", "GET", "/api/history", 200, None),
        ("summarize no-op allowed", "POST", "/api/summarize", 200, {}),
        ("documents denied", "GET", "/api/documents", 403, None),
        ("notice denied", "GET", "/admin/notice-documents", 403, None),
        ("ocr denied", "GET", "/ocr/supported-formats", 403, None),
    ]
    for name, method, path, expected, payload in leader_checks:
        result = request(method, path, leader_token, payload)
        record(results, "DEPARTMENT_LEADER", name, method, path, result, expected)

    staff_checks = [
        ("me", "GET", "/auth/me", 200, None),
        ("cannot manage users", "GET", "/admin/users", 403, None),
        ("work documents denied", "GET", "/admin/work-documents", 403, None),
        ("list assigned work items", "GET", "/admin/work-items", 200, None),
        ("create work item denied", "POST", "/admin/work-items", 403, {
            "work_document_id": doc_id,
            "title": "Staff cannot create",
            "department_id": ids["department_id"],
        } if doc_id else {}),
        ("api supported formats", "GET", "/api/supported-formats", 200, None),
        ("summarize no-op allowed", "POST", "/api/summarize", 200, {}),
        ("documents denied", "GET", "/api/documents", 403, None),
        ("search denied", "POST", "/api/search", 403, {"query": "test", "top_k": 1}),
        ("history denied", "GET", "/api/history", 403, None),
        ("ocr supported formats", "GET", "/ocr/supported-formats", 200, None),
        ("ocr analyze text", "POST", "/ocr/analyze-text", 200, {"text": "Cong van so 01 ve ke hoach thang 6."}),
        ("ocr search denied", "POST", "/ocr/search", 403, {"query": "test", "top_k": 1}),
        ("notice denied", "GET", "/admin/notice-documents", 403, None),
    ]
    for name, method, path, expected, payload in staff_checks:
        result = request(method, path, staff_token, payload)
        record(results, "STAFF", name, method, path, result, expected)

    if item_id:
        staff_update = request("PUT", f"/admin/work-items/{item_id}", staff_token, {"status": "done"})
        staff_delete = request("DELETE", f"/admin/work-items/{item_id}", staff_token)
        record(results, "STAFF", "update work item denied by service scope", "PUT", f"/admin/work-items/{item_id}", staff_update, 403)
        record(results, "STAFF", "delete work item denied by service scope", "DELETE", f"/admin/work-items/{item_id}", staff_delete, 403)
        leader_cleanup_item = request("DELETE", f"/admin/work-items/{item_id}", leader_token)
        record(results, "DEPARTMENT_LEADER", "cleanup assigned work item", "DELETE", f"/admin/work-items/{item_id}", leader_cleanup_item, 200)

    if doc_id:
        deleted_doc = request("DELETE", f"/admin/work-documents/{doc_id}", leader_token)
        record(results, "DEPARTMENT_LEADER", "delete work document", "DELETE", f"/admin/work-documents/{doc_id}", deleted_doc, 200)

    write_results(stamp, ids, {"leader": leader_payload, "staff": staff_payload}, results)
    return 0 if all(item["ok"] for item in results) else 1


def write_results(stamp: str, ids: dict, users: dict, results: list[dict]) -> None:
    output = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "base_url": BASE_URL,
        "seed_context": ids,
        "created_users": users,
        "summary": {
            "total": len(results),
            "passed": sum(1 for item in results if item["ok"]),
            "failed": sum(1 for item in results if not item["ok"]),
        },
        "results": results,
    }
    with open("role_e2e_results.json", "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    with open(f"role_e2e_results_{stamp}.json", "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    with open("created_test_users.json", "w", encoding="utf-8") as fh:
        json.dump(users, fh, ensure_ascii=False, indent=2)
    print(json.dumps(output["summary"], ensure_ascii=False))


if __name__ == "__main__":
    time.sleep(0.2)
    sys.exit(main())
