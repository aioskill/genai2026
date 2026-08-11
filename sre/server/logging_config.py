from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


_RESERVED = frozenset(
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
        "processName",
        "process",
        "asctime",
        "message",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Format gateway records as single-line JSON for log collectors."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if (
                key not in payload
                and key not in _RESERVED
                and not key.startswith("_")
                and value is not None
            ):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def _file_handler(path: str, level: int) -> RotatingFileHandler | None:
    try:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(target, maxBytes=10 * 1024 * 1024, backupCount=5)
        handler.setLevel(level)
        handler.setFormatter(JsonFormatter())
        return handler
    except OSError:
        logging.getLogger("sre_gateway").warning("Unable to open log file: %s", path)
        return None


def configure_logging(settings: Any) -> None:
    """Configure console, gateway, and audit logging from gateway settings."""
    gateway = settings.gateway
    level = getattr(
        logging, str(gateway.get("log_level", "INFO")).upper(), logging.INFO
    )
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(console)

    mcp_logger = logging.getLogger("mcp")
    mcp_logger.setLevel(logging.INFO)
    mcp_logger.propagate = False
    mcp_console = logging.StreamHandler()
    mcp_console.setLevel(logging.INFO)
    mcp_console.setFormatter(
        logging.Formatter("%(asctime)s INFO %(name)s: %(message)s")
    )
    mcp_logger.addHandler(mcp_console)

    gateway_handler = _file_handler(
        gateway.get("log_path", "./var/mcp-gateway.log"), level
    )
    if gateway_handler:
        root.addHandler(gateway_handler)

    audit_handler = _file_handler(
        gateway.get("audit_log_path", "./var/audit.log"), logging.INFO
    )
    if audit_handler:
        audit_logger = logging.getLogger("sre_gateway.audit")
        audit_logger.setLevel(logging.INFO)
        audit_logger.propagate = False
        audit_logger.handlers.clear()
        audit_logger.addHandler(audit_handler)
