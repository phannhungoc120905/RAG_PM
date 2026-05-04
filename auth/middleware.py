import json
import time

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from auth.service import decode_token
from db.database import SessionLocal
from db.models import SystemLog


EXCLUDED_PATHS = {"/docs", "/redoc", "/openapi.json", "/health"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)

        if request.url.path in EXCLUDED_PATHS:
            return response

        try:
            db = SessionLocal()
            try:
                user_id = self._extract_user_id(request)
                detail = self._build_detail(request, start_time)
                db.add(
                    SystemLog(
                        user_id=user_id,
                        action=f"{request.method} {request.url.path}",
                        detail=detail,
                        ip_address=request.client.host if request.client else None,
                        status_code=response.status_code,
                    )
                )
                db.commit()
            finally:
                db.close()
        except Exception:
            pass

        return response

    def _extract_user_id(self, request: Request) -> int | None:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            payload = decode_token(token)
            return int(payload["sub"])
        except Exception:
            return None

    def _build_detail(self, request: Request, start_time: float) -> str | None:
        query_params = dict(request.query_params)
        payload = {
            "query_params": query_params or None,
            "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 2),
        }
        return json.dumps(payload, ensure_ascii=False)


def add_middlewares(app: FastAPI) -> None:
    app.add_middleware(RequestLoggingMiddleware)
