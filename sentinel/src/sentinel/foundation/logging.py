"""Pipeline de logging JSON a stdout (P4 — BR-09..BR-12).

Cada línea es un objeto JSON con los campos obligatorios ``ts`` (ISO 8601
UTC), ``level``, ``component``, ``event`` y ``msg``; los pares extra pasados
por ``extra={...}`` se serializan como JSON adicional. Nunca archivo ni
stderr (el logging de Kubernetes captura stdout).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from sentinel.foundation.config import load_settings

__all__ = ["JsonFormatter", "get_logger"]

_STD_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "process",
        "processName",
        "taskName",
        "message",
        "asctime",
    }
)

_FALLBACK_EVENT = "unnamed"


class JsonFormatter(logging.Formatter):
    """Serializa cada ``LogRecord`` como una línea JSON con los 5 campos."""

    def format(self, record: logging.LogRecord) -> str:
        component = getattr(record, "component", None) or record.name.removeprefix("sentinel.")
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "component": component,
            "event": getattr(record, "event", None) or _FALLBACK_EVENT,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STD_RECORD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def get_logger(component: str) -> logging.Logger:
    """Devuelve el logger JSON del ``component`` (handler único, BR-12).

    Idempotente: dos llamadas con el mismo ``component`` devuelven el mismo
    logger con exactamente un handler ``StreamHandler(stdout)``.
    """
    name = f"sentinel.{component}"
    logger = logging.getLogger(name)
    logger.setLevel(load_settings().log_level)

    if not any(
        isinstance(h, logging.StreamHandler) and h.stream is sys.stdout for h in logger.handlers
    ):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    for existing in logger.handlers:
        if isinstance(existing, logging.StreamHandler) and existing.stream is sys.stdout:
            existing.setLevel(logger.level)

    return logger
