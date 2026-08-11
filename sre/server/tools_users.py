import re
from .core import *

USERNAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,31}$")


def _create_script(username, groups, key):
    script = "set -e\n"
    script += "/usr/sbin/useradd -m"
    if groups:
        script += " -G " + ",".join(groups)
    script += ' "$1"\n'
    if key:
        script += (
            'install -d -m 700 -o "$1" -g "$1" /home/"$1"/.ssh\n'
            'printf "%s\\n" "$2" > /home/"$1"/.ssh/authorized_keys\n'
            'chown -R "$1":"$1" /home/"$1"/.ssh\n'
            'chmod 700 /home/"$1"/.ssh\n'
            'chmod 600 /home/"$1"/.ssh/authorized_keys\n'
        )
    return ["/usr/bin/bash", "-c", script, "bash", username, key or ""]


def _disable_script(username, terminate_processes):
    script = "/usr/sbin/usermod -L \"$1\"\n"
    if terminate_processes:
        script += 'pkill -u "$1" 2>/dev/null || true\n'
    return ["/usr/bin/bash", "-c", script, "bash", username]


def register(mcp, settings):
    @mcp.tool()
    def list_system_users(
        server_id: str | None = None, tags: list[str] | None = None
    ) -> dict:
        """List system users without exposing password hashes."""
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {"raw": run_ssh(settings, n, ["/usr/bin/getent", "passwd"])},
        )

    @mcp.tool()
    def get_recent_logins(
        server_id: str | None = None,
        tags: list[str] | None = None,
        login_type: str = "all",
        username: str | None = None,
        limit: int = 50,
    ) -> dict:
        """Read bounded login history."""
        if (
            login_type not in {"successful", "failed", "currently_logged_in", "all"}
            or not 1 <= limit <= 200
        ):
            raise GatewayError("INVALID_ARGUMENT", "login filters are invalid")
        command = {
            "successful": "last",
            "failed": "lastb",
            "currently_logged_in": "who",
            "all": "last",
        }[login_type]
        args = ["/usr/bin/" + command]
        if username and command != "who":
            if not USERNAME_RE.match(username):
                raise GatewayError("INVALID_USERNAME", "username is invalid")
            args.append(username)
        args += ["-n", str(limit)] if command != "who" else []
        return read_only(
            settings, server_id, tags, lambda n: {"raw": run_ssh(settings, n, args)}
        )

    @mcp.tool()
    def create_system_user(
        server_id: str | None = None,
        tags: list[str] | None = None,
        username: str = "",
        groups: list[str] | None = None,
        ssh_public_key: str | None = None,
        dry_run: bool = True,
    ) -> dict:
        """Create a system user."""
        if not username or not USERNAME_RE.match(username):
            raise GatewayError("INVALID_USERNAME", "username is invalid")
        if dry_run:
            return envelope(
                "dry_run_preview",
                "single" if server_id else "multi_tag",
                server_id=server_id,
                dry_run=True,
                data={
                    "action": "create",
                    "username": username,
                    "groups": groups or [],
                    "ssh_public_key_supplied": bool(ssh_public_key),
                },
            )
        argv = _create_script(username, groups or [], ssh_public_key or "")
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {"raw": run_ssh(settings, n, argv, privileged=True)},
        )

    @mcp.tool()
    def disable_system_user(
        server_id: str | None = None,
        tags: list[str] | None = None,
        username: str = "",
        terminate_processes: bool = True,
        dry_run: bool = True,
    ) -> dict:
        """Disable a system user."""
        if not username or not USERNAME_RE.match(username):
            raise GatewayError("INVALID_USERNAME", "username is invalid")
        if dry_run:
            return envelope(
                "dry_run_preview",
                "single" if server_id else "multi_tag",
                server_id=server_id,
                dry_run=True,
                data={"action": "disable", "username": username},
            )
        argv = _disable_script(username, terminate_processes)
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {"raw": run_ssh(settings, n, argv, privileged=True)},
        )

    @mcp.tool()
    def enable_system_user(
        server_id: str | None = None,
        tags: list[str] | None = None,
        username: str = "",
        dry_run: bool = True,
    ) -> dict:
        """Enable a system user."""
        if not username or not USERNAME_RE.match(username):
            raise GatewayError("INVALID_USERNAME", "username is invalid")
        if dry_run:
            return envelope(
                "dry_run_preview",
                "single" if server_id else "multi_tag",
                server_id=server_id,
                dry_run=True,
                data={"action": "enable", "username": username},
            )
        argv = ["/usr/sbin/usermod", "-U", username]
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {"raw": run_ssh(settings, n, argv, privileged=True)},
        )

    @mcp.tool()
    def remove_system_user(
        server_id: str | None = None,
        tags: list[str] | None = None,
        username: str = "",
        archive_home: bool = True,
        dry_run: bool = True,
    ) -> dict:
        """Remove a system user."""
        if not username or not USERNAME_RE.match(username):
            raise GatewayError("INVALID_USERNAME", "username is invalid")
        if dry_run:
            return envelope(
                "dry_run_preview",
                "single" if server_id else "multi_tag",
                server_id=server_id,
                dry_run=True,
                data={"action": "remove", "username": username},
            )
        argv = ["/usr/sbin/userdel"]
        if not archive_home:
            argv.append("-r")
        argv.append(username)
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {"raw": run_ssh(settings, n, argv, privileged=True)},
        )
