import re
import posixpath
import fnmatch
from datetime import datetime, timezone
from .core import *
from pathlib import PurePosixPath

UNIT_RE = re.compile(r"^[A-Za-z0-9_.@+\-]+$")
SINCE_RE = re.compile(r"^[A-Za-z0-9 :.,+\-]+$")


def _denied_path(settings, path_str: str) -> bool:
    denied = settings.gateway.get("denied_paths", [])
    patterns = settings.gateway.get("denied_patterns", [])
    if any(
        path_str == x or path_str.startswith(x.rstrip("/") + "/") for x in denied
    ):
        return True
    for pat in patterns:
        matches = [pat, pat[:-2]] if pat.endswith("/*") else [pat]
        if any(fnmatch.fnmatch(path_str, m) for m in matches):
            return True
    return False


def safe_path(settings, path: str) -> str:
    if not path:
        raise GatewayError("INVALID_PATH", "path must be absolute")
    p = PurePosixPath(path)
    if not p.is_absolute():
        raise GatewayError("INVALID_PATH", "path must be absolute")
    path_str = posixpath.normpath(str(p))
    if _denied_path(settings, path_str):
        raise GatewayError("PATH_DENIED", f"Access denied: {path}")
    if not settings.gateway.get("enforce_path_sandbox", True):
        return path_str
    approved = getattr(settings, "approved_paths", {})
    if path_str in approved or any(
        path_str.startswith(root.rstrip("/") + "/") for root in approved
    ):
        return path_str
    if not any(
        path_str == root or path_str.startswith(root.rstrip("/") + "/")
        for root in settings.allowed_roots
    ):
        raise GatewayError(
            "PATH_OUTSIDE_SANDBOX",
            f"Path is outside allowed roots: {path}. "
            "Ask the operator to approve access with the 'approve_path_access' tool.",
        )
    return path_str


def register(mcp, settings):
    @mcp.tool()
    def list_directory(
        server_id: str | None = None,
        tags: list[str] | None = None,
        path: str = "/var/log",
        recursive: bool = False,
        max_depth: int = 2,
    ) -> dict:
        """List a sandboxed directory with bounded recursion."""
        path = safe_path(settings, path)
        if not 0 <= max_depth <= 5:
            raise GatewayError("RESOURCE_LIMIT", "max_depth must be between 0 and 5")
        depth = max_depth if recursive else 1
        entry_limit = min(
            int(settings.gateway.get("directory_entry_limit", 1000)), 10000
        )
        find_args = [
            "/usr/bin/find",
            path,
            "-maxdepth",
            str(depth),
            "-xdev",
            "-print",
        ]

        def op(n):
            raw = run_ssh(settings, n, find_args)
            lines = raw["stdout"].splitlines()
            if len(lines) > entry_limit:
                raw["stdout"] = "\n".join(lines[:entry_limit]) + "\n"
                raw["truncated"] = True
                raw["truncated_entries"] = len(lines) - entry_limit
            else:
                raw["truncated"] = False
            return {"raw": raw}

        return read_only(settings, server_id, tags, op)

    @mcp.tool()
    def read_file_head_tail(
        server_id: str | None = None,
        tags: list[str] | None = None,
        path: str = "/var/log/syslog",
        mode: str = "tail",
        lines: int = 50,
    ) -> dict:
        """Read bounded head or tail lines from a sandboxed text file."""
        path = safe_path(settings, path)
        if mode not in ("head", "tail") or not 1 <= lines <= 500:
            raise GatewayError(
                "INVALID_ARGUMENT", "mode must be head/tail and lines 1..500"
            )
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {
                "raw": run_ssh(
                    settings, n, ["/usr/bin/" + mode, "-n", str(lines), "--", path]
                )
            },
        )

    @mcp.tool()
    def grep_file(
        server_id: str | None = None,
        tags: list[str] | None = None,
        path: str = "/var/log/syslog",
        pattern: str = "",
        max_matches: int = 100,
    ) -> dict:
        """Search a sandboxed text file with bounded output."""
        path = safe_path(settings, path)
        pattern_limit = min(
            int(settings.gateway.get("regex_pattern_limit", 4096)), 16384
        )
        if (
            not pattern
            or len(pattern) > pattern_limit
            or not 1 <= max_matches <= 500
        ):
            raise GatewayError(
                "INVALID_ARGUMENT", "pattern and max_matches are invalid"
            )
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {
                "raw": run_ssh(
                    settings,
                    n,
                    [
                        "/usr/bin/grep",
                        "-E",
                        "-m",
                        str(max_matches),
                        "--",
                        pattern,
                        path,
                    ],
                )
            },
        )

    @mcp.tool()
    def read_journal_logs(
        server_id: str | None = None,
        tags: list[str] | None = None,
        unit_name: str = "",
        since: str = "1h",
        priority: str = "info",
        lines: int = 100,
    ) -> dict:
        """Read bounded systemd journal entries for a unit."""
        if not unit_name or not UNIT_RE.match(unit_name):
            raise GatewayError("INVALID_ARGUMENT", "unit_name is invalid")
        if not since or len(since) > 64 or not SINCE_RE.match(since):
            raise GatewayError("INVALID_ARGUMENT", "since filter is invalid")
        if (
            priority
            not in {
                "emerg",
                "alert",
                "crit",
                "err",
                "warning",
                "notice",
                "info",
                "debug",
            }
            or not 1 <= lines <= 500
        ):
            raise GatewayError("INVALID_ARGUMENT", "journal filters are invalid")
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {
                "raw": run_ssh(
                    settings,
                    n,
                    [
                        "/usr/bin/journalctl",
                        "-u",
                        unit_name,
                        "--since",
                        since,
                        "-p",
                        priority,
                        "-n",
                        str(lines),
                        "--no-pager",
                    ],
                )
            },
        )

    @mcp.tool()
    def get_activity_logs(
        task_id: str | None = None,
        server_id: str | None = None,
        tags: list[str] | None = None,
        tool_name: str | None = None,
        status: str = "all",
        since: str = "1h",
        limit: int = 50,
    ) -> dict:
        """Query gateway activity records; persistence is enabled when the scheduler store is configured."""
        if (
            status not in {"running", "completed", "failed", "cancelled", "all"}
            or not 1 <= limit <= 200
        ):
            raise GatewayError("INVALID_ARGUMENT", "activity filters are invalid")
        return {
            "status": "error",
            "target_type": "gateway",
            "dry_run": False,
            "error": {
                "code": "ACTIVITY_STORE_NOT_CONFIGURED",
                "message": "Configure the scheduler activity store before querying activity logs",
            },
        }

    @mcp.tool()
    def list_scheduled_tasks(
        server_id: str | None = None,
        tags: list[str] | None = None,
        status: str = "pending",
    ) -> dict:
        """List deferred tasks; persistence is enabled when the scheduler store is configured."""
        if status not in {"pending", "executing", "completed", "cancelled", "all"}:
            raise GatewayError("INVALID_ARGUMENT", "invalid scheduled-task status")
        return {
            "status": "error",
            "target_type": "gateway",
            "dry_run": False,
            "error": {
                "code": "SCHEDULER_NOT_CONFIGURED",
                "message": "Configure the scheduler store before querying scheduled tasks",
            },
        }

    @mcp.tool()
    def approve_path_access(path: str = "", reason: str = "", dry_run: bool = True) -> dict:
        """Preview or grant operator-approved runtime access to a path outside the configured allowed roots (HITL)."""
        if not path:
            raise GatewayError("INVALID_PATH", "path must be absolute")
        p = PurePosixPath(path)
        if not p.is_absolute():
            raise GatewayError("INVALID_PATH", "path must be absolute")
        path_str = posixpath.normpath(str(p))
        if _denied_path(settings, path_str):
            raise GatewayError(
                "PATH_DENIED", f"Access cannot be approved for a denied path: {path}"
            )
        if dry_run:
            return envelope(
                "dry_run_preview",
                "gateway",
                dry_run=True,
                data={
                    "action": "approve_path_access",
                    "path": path_str,
                    "reason": reason,
                },
            )
        settings.approved_paths[path_str] = {
            "reason": reason,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }
        return envelope(
            "success",
            "gateway",
            dry_run=False,
            data={"approved_path": path_str, "reason": reason},
        )

    @mcp.tool()
    def list_approved_paths() -> dict:
        """List paths that have been approved for runtime access."""
        entries = [
            {
                "path": path_str,
                "reason": meta.get("reason", ""),
                "approved_at": meta.get("approved_at", ""),
            }
            for path_str, meta in settings.approved_paths.items()
        ]
        return envelope("success", "gateway", data={"approved_paths": entries})

    @mcp.tool()
    def revoke_path_access(path: str = "") -> dict:
        """Revoke a previously approved runtime path."""
        path_str = posixpath.normpath(str(PurePosixPath(path))) if path else ""
        revoked = path_str in settings.approved_paths
        settings.approved_paths.pop(path_str, None)
        return envelope(
            "success",
            "gateway",
            dry_run=False,
            data={"revoked_path": path_str, "was_approved": revoked},
        )
