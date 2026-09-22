from __future__ import annotations
import json, logging, shlex, subprocess, time, uuid
from pathlib import Path
from dataclasses import asdict
from typing import Any
from .config import Settings, Server

log = logging.getLogger("sre_gateway")


class GatewayError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def envelope(
    status: str,
    target_type: str,
    *,
    server_id=None,
    matching_nodes=None,
    dry_run=False,
    data=None,
    results=None,
    summary=None,
    error=None,
    **extra,
):
    value = {"status": status, "target_type": target_type, "dry_run": dry_run}
    if server_id is not None:
        value["server_id"] = server_id
    if matching_nodes is not None:
        value["matching_nodes"] = matching_nodes
    if summary is not None:
        value["summary"] = summary
    if data is not None:
        value["data"] = data
    if results is not None:
        value["results"] = results
    if error is not None:
        value["error"] = error
    value.update(extra)
    return value


def select_nodes(
    settings: Settings, server_id: str | None = None, tags: list[str] | None = None
) -> tuple[str, list[Server]]:
    if bool(server_id) == bool(tags):
        raise GatewayError(
            "INVALID_TARGETING_SPEC", "Provide exactly one of server_id or tags"
        )
    if server_id:
        node = settings.servers.get(server_id)
        if not node or not node.enabled:
            raise GatewayError(
                "UNKNOWN_SERVER", f"Server is not enabled or registered: {server_id}"
            )
        return "single", [node]
    wanted = set(tags or [])
    nodes = [
        node
        for node in settings.servers.values()
        if node.enabled and wanted.issubset(set(node.tags))
    ]
    if not nodes:
        raise GatewayError(
            "NO_MATCHING_NODES", "No enabled servers match the requested tags"
        )
    maximum = int(settings.gateway.get("max_request_nodes", 200))
    if len(nodes) > maximum:
        raise GatewayError(
            "FLEET_LIMIT_EXCEEDED",
            f"Selector matches {len(nodes)} nodes; maximum is {maximum}",
        )
    return "multi_tag", nodes


def result_for(
    selector: str, nodes: list[Server], results: dict[str, Any], dry_run=False
):
    ok = sum(item.get("status") == "success" for item in results.values())
    failed = len(results) - ok
    status = "success" if failed == 0 else ("error" if ok == 0 else "partial_success")
    common = dict(
        dry_run=dry_run,
        results=results,
        summary={
            "total_nodes": len(nodes),
            "succeeded_nodes": ok,
            "failed_nodes": failed,
        },
    )
    return envelope(
        status,
        selector,
        server_id=nodes[0].id if selector == "single" else None,
        matching_nodes=[n.id for n in nodes] if selector == "multi_tag" else None,
        **common,
    )


def run_ssh(
    settings: Settings,
    node: Server,
    argv: list[str],
    *,
    timeout: int | None = None,
    privileged: bool = False,
) -> dict[str, Any]:
    if not argv or any("\x00" in part for part in argv):
        raise GatewayError("INVALID_COMMAND", "Empty command or NUL byte")
    if privileged and not settings.ssh.get("passwordless_sudo", False):
        raise GatewayError(
            "PRIVILEGE_DISABLED",
            "Passwordless sudo is disabled in the gateway config. "
            "Enable ssh.passwordless_sudo in server/config.yaml to run "
            "privileged operations.",
        )
    command = shlex.join(["sudo", "-n", *argv] if privileged else argv)
    ssh = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={int(settings.gateway.get('ssh_connect_timeout_seconds', 10))}",
    ]
    if settings.ssh.get("strict_host_key_checking", True):
        ssh += ["-o", "StrictHostKeyChecking=yes"]
    known_hosts = settings.ssh.get("known_hosts_path")
    if known_hosts:
        ssh += ["-o", f"UserKnownHostsFile={Path(known_hosts).expanduser()}"]
    ssh += [
        "-p",
        str(node.port),
        f"{settings.gateway.get('ssh_user', 'mcp-agent')}@{node.host}",
        command,
    ]
    started = time.monotonic()
    log.info("SSH method call: %s", command)
    logging.getLogger("sre_gateway.audit").info(
        "SSH method call",
        extra={
            "node_id": node.id,
            "node_host": node.host,
            "node_port": node.port,
            "command": command,
        },
    )
    try:
        completed = subprocess.run(
            ssh,
            capture_output=True,
            text=True,
            timeout=timeout
            or int(settings.gateway.get("ssh_command_timeout_seconds", 120)),
        )
    except subprocess.TimeoutExpired as exc:
        raise GatewayError(
            "REMOTE_COMMAND_TIMEOUT", f"Command timed out on {node.id}"
        ) from exc
    except OSError as exc:
        raise GatewayError("SSH_EXECUTION_FAILED", str(exc)) from exc
    if completed.returncode:
        stderr = completed.stderr[-4096:].strip()
        known_hosts = settings.ssh.get("known_hosts_path")
        known_hosts_path = str(Path(known_hosts).expanduser()) if known_hosts else None
        stderr_upper = stderr.upper()
        is_mismatch = (
            "HOST IDENTIFICATION HAS CHANGED" in stderr_upper
            or "REMOTE HOST IDENTIFICATION HAS CHANGED" in stderr_upper
            or ("OFFENDING" in stderr_upper and "KNOWN HOSTS" in stderr_upper)
            or "PRESENTED KEY DOES NOT MATCH" in stderr_upper
        )
        is_unknown = "NO HOST KEY IS KNOWN" in stderr_upper or (
            "HOST KEY VERIFICATION FAILED" in stderr_upper
            and not is_mismatch
        )
        stderr_lower = stderr.lower()
        if is_mismatch:
            code = "SSH_HOST_KEY_MISMATCH"
        elif is_unknown:
            code = "SSH_HOST_KEY_UNKNOWN"
        elif "permission denied" in stderr_lower and (
            "publickey" in stderr_lower or "please try again" in stderr_lower
        ):
            code = "SSH_AUTH_FAILED"
        elif (
            "interactive authentication required" in stderr_lower
            or "not authorized" in stderr_lower
            or "authorization not available" in stderr_lower
            or "polkit" in stderr_lower
            or "password is required" in stderr_lower
            or "you must have a tty" in stderr_lower
        ):
            code = "REMOTE_PRIVILEGE_REQUIRED"
        else:
            code = "REMOTE_COMMAND_FAILED"
        if code == "SSH_HOST_KEY_MISMATCH":
            message = (
                f"SSH host key verification failed for {node.id} ({node.host}:{node.port}). "
                "The stored host key does not match the key presented by the server. "
                f"Review and update the pinned entry in {known_hosts_path or 'the configured known_hosts file'} "
                "after verifying the fingerprint with the administrator."
            )
            raise GatewayError(code, message)
        if code == "SSH_HOST_KEY_UNKNOWN":
            message = (
                f"SSH host key verification failed for {node.id} ({node.host}:{node.port}). "
                "No host key is pinned in the known_hosts file. Pin the server's host key "
                f"in {known_hosts_path or 'the configured known_hosts file'} "
                "after verifying the fingerprint with the administrator."
            )
            raise GatewayError(code, message)
        if code == "REMOTE_PRIVILEGE_REQUIRED":
            ssh_user = settings.gateway.get("ssh_user", "mcp-agent")
            message = (
                f"Privilege escalation failed on {node.id} ({node.host}). "
                f"The SSH user {ssh_user} is not authorized to run '{command}' "
                "non-interactively. Grant that user passwordless sudo (or a polkit "
                "rule for systemctl), then retry."
            )
            raise GatewayError(code, message)
        raise GatewayError(code, stderr or f"ssh exited with {completed.returncode}")
    return {
        "stdout": completed.stdout[-1048576:],
        "duration_ms": round((time.monotonic() - started) * 1000),
    }


def call_nodes(
    settings: Settings, selector: str, nodes: list[Server], operation, *, dry_run=False
):
    results = {}
    for node in nodes:
        try:
            results[node.id] = {"status": "success", "data": operation(node)}
        except GatewayError as exc:
            results[node.id] = {
                "status": "error",
                "error": {"code": exc.code, "message": exc.message},
            }
        except Exception as exc:
            log.exception("node operation failed")
            results[node.id] = {
                "status": "error",
                "error": {"code": "INTERNAL_ERROR", "message": str(exc)},
            }
    return result_for(selector, nodes, results, dry_run=dry_run)


def read_only(settings, server_id, tags, operation):
    selector, nodes = select_nodes(settings, server_id, tags)
    return call_nodes(settings, selector, nodes, operation)
