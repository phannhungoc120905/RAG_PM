import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


_RESERVED_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "taskName",
    "thread",
    "threadName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }

        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_FIELDS and not key.startswith("_")
        }
        payload.update(extra_fields)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class JsonLogger(logging.Logger):
    def _merge_extra(
        self, extra: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any] | None:
        merged = dict(extra or {})
        merged.update(kwargs)
        safe_merged = {
            key if key not in _RESERVED_FIELDS else f"extra_{key}": value
            for key, value in merged.items()
        }
        return safe_merged or None

    def debug(self, msg: Any, *args: Any, extra: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().debug(msg, *args, extra=self._merge_extra(extra, **kwargs))

    def info(self, msg: Any, *args: Any, extra: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().info(msg, *args, extra=self._merge_extra(extra, **kwargs))

    def warning(self, msg: Any, *args: Any, extra: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().warning(msg, *args, extra=self._merge_extra(extra, **kwargs))

    def error(self, msg: Any, *args: Any, extra: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().error(msg, *args, extra=self._merge_extra(extra, **kwargs))

    def critical(self, msg: Any, *args: Any, extra: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().critical(msg, *args, extra=self._merge_extra(extra, **kwargs))

    def exception(self, msg: Any, *args: Any, extra: dict[str, Any] | None = None, exc_info: Any = True, **kwargs: Any) -> None:
        super().exception(
            msg,
            *args,
            extra=self._merge_extra(extra, **kwargs),
            exc_info=exc_info,
        )


logging.setLoggerClass(JsonLogger)


def get_logger(module_name: str) -> logging.Logger:
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    return logger
