from __future__ import annotations

import logging
import time
import uuid
from functools import wraps
from typing import Any, Callable

from fastmcp import FastMCP

from .core import GatewayError, envelope

log = logging.getLogger("sre_gateway")

_SENSITIVE_KEYS = (
    "ssh_public_key",
    "unit_content",
    "extra_vars",
    "password",
    "secret",
    "token",
    "private_key",
    "authorization",
)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("<redacted>" if any(s in key.lower() for s in _SENSITIVE_KEYS) else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _audit(message: str, **fields: Any) -> None:
    logging.getLogger("sre_gateway.audit").info(message, extra=fields)


class SafeFastMCP(FastMCP):
    """FastMCP server that turns tool exceptions into contract responses."""

    def tool(self, *args: Any, **kwargs: Any) -> Callable:
        register = super().tool(*args, **kwargs)

        def decorator(function: Callable) -> Any:
            @wraps(function)
            def guarded(*function_args: Any, **function_kwargs: Any) -> Any:
                started = time.monotonic()
                tool_name = function.__name__
                target_type = (
                    "single"
                    if function_kwargs.get("server_id")
                    else "multi_tag" if function_kwargs.get("tags") else "gateway"
                )
                redacted_args = _redact(function_kwargs)
                detail = (
                    ", ".join(f"{key}={value!r}" for key, value in redacted_args.items())
                    if redacted_args
                    else "no arguments"
                )
                log.info("MCP method call: %s(%s)", tool_name, detail)
                _audit(
                    "MCP method call",
                    tool_name=tool_name,
                    target_type=target_type,
                    server_id=function_kwargs.get("server_id"),
                    matching_nodes=function_kwargs.get("tags"),
                    arguments=redacted_args,
                )
                try:
                    result = function(*function_args, **function_kwargs)
                    _log_request(
                        tool_name, function_kwargs, target_type, result, started
                    )
                    return result
                except GatewayError as exc:
                    result = _error_response(function_kwargs, exc.code, exc.message)
                    _log_request(
                        tool_name, function_kwargs, target_type, result, started
                    )
                    return result
                except Exception:
                    error_id = str(uuid.uuid4())
                    log.exception(
                        "Unhandled MCP tool failure",
                        extra={"error_id": error_id, "tool_name": function.__name__},
                    )
                    result = _error_response(
                        function_kwargs,
                        "INTERNAL_ERROR",
                        f"The request failed. Contact the operator with error_id {error_id}.",
                    )
                    _log_request(
                        tool_name,
                        function_kwargs,
                        target_type,
                        result,
                        started,
                        error_id=error_id,
                    )
                    return result

            return register(guarded)

        return decorator


def _error_response(
    arguments: dict[str, Any], code: str, message: str
) -> dict[str, Any]:
    server_id = arguments.get("server_id")
    tags = arguments.get("tags")
    target_type = "single" if server_id else "multi_tag" if tags else "gateway"
    return envelope(
        "error",
        target_type,
        server_id=server_id,
        matching_nodes=tags if target_type == "multi_tag" else None,
        dry_run=bool(arguments.get("dry_run", False)),
        error={"code": code, "message": message},
    )


def _log_request(
    tool_name: str,
    arguments: dict[str, Any],
    target_type: str,
    result: Any,
    started: float,
    error_id: str | None = None,
) -> None:
    status = result.get("status") if isinstance(result, dict) else "success"
    error = result.get("error", {}) if isinstance(result, dict) else {}
    fields = {
        "tool_name": tool_name,
        "target_type": target_type,
        "server_id": arguments.get("server_id"),
        "matching_nodes": arguments.get("tags"),
        "status": status,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "error_code": error.get("code"),
        "error_id": error_id,
    }
    log.info(
        "MCP tool request completed",
        extra={key: value for key, value in fields.items() if value is not None},
    )
    logging.getLogger("sre_gateway.audit").info(
        "MCP tool audit event",
        extra={key: value for key, value in fields.items() if value is not None},
    )
