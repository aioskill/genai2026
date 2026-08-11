import json
from .core import *


def register(mcp, settings):
    @mcp.tool()
    def list_available_playbooks() -> dict:
        """List approved playbooks configured by the deployment."""
        return {
            "status": "success",
            "target_type": "gateway",
            "dry_run": False,
            "data": {"playbooks": settings.raw.get("approved_playbooks", [])},
        }

    @mcp.tool()
    def cancel_scheduled_task(task_id: str, reason: str) -> dict:
        """Cancel a scheduled task; scheduler persistence is enabled in the next runtime layer."""
        if not task_id or not reason:
            raise GatewayError("INVALID_ARGUMENT", "task_id and reason are required")
        return {
            "status": "error",
            "target_type": "gateway",
            "dry_run": False,
            "error": {
                "code": "SCHEDULER_NOT_CONFIGURED",
                "message": "Configure a persistent scheduler before cancellation is enabled",
            },
        }

    def preview_automation(server_id, tags, dry_run, data, argv):
        if dry_run:
            return envelope(
                "dry_run_preview",
                "single" if server_id else "multi_tag",
                server_id=server_id,
                dry_run=True,
                data=data,
            )
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {"raw": run_ssh(settings, n, argv, privileged=True)},
        )

    @mcp.tool()
    def run_system_patching(
        server_id: str | None = None,
        tags: list[str] | None = None,
        reboot_if_needed: bool = False,
        dry_run: bool = True,
    ) -> dict:
        """Apply available system package updates."""
        script = (
            'apt-get -y -o Dpkg::Options::=--force-confold upgrade\n'
            'if [ "$1" = "true" ] && [ -f /var/run/reboot-required ]; then '
            'systemctl reboot; fi\n'
        )
        argv = [
            "/usr/bin/bash",
            "-c",
            script,
            "bash",
            "true" if reboot_if_needed else "false",
        ]
        return preview_automation(
            server_id,
            tags,
            dry_run,
            {"reboot_if_needed": reboot_if_needed},
            argv,
        )

    @mcp.tool()
    def run_package_installer(
        server_id: str | None = None,
        tags: list[str] | None = None,
        packages: list[str] | None = None,
        state: str = "present",
        dry_run: bool = True,
    ) -> dict:
        """Install, update, or remove system packages."""
        if state not in {"present", "latest", "absent"}:
            raise GatewayError(
                "INVALID_STATE", "state must be present, latest, or absent"
            )
        pkgs = packages or []
        if not pkgs:
            raise GatewayError("INVALID_ARGUMENT", "packages list must not be empty")
        action = {"present": "install", "latest": "install", "absent": "remove"}[state]
        argv = ["/usr/bin/apt-get", "-y", action]
        if state == "latest":
            argv.append("--only-upgrade")
        argv += pkgs
        return preview_automation(
            server_id,
            tags,
            dry_run,
            {"packages": pkgs, "state": state},
            argv,
        )

    @mcp.tool()
    def execute_playbook(
        server_id: str | None = None,
        tags: list[str] | None = None,
        playbook_name: str = "",
        extra_vars: dict | None = None,
        dry_run: bool = True,
    ) -> dict:
        """Execute an approved playbook via ansible-playbook."""
        if not playbook_name:
            raise GatewayError("INVALID_PLAYBOOK", "playbook_name is required")
        approved = settings.raw.get("approved_playbooks", [])
        if playbook_name not in approved:
            raise GatewayError(
                "PLAYBOOK_NOT_APPROVED",
                f"Playbook is not approved: {playbook_name}",
            )
        argv = ["/usr/bin/ansible-playbook", playbook_name]
        if extra_vars:
            argv += ["-e", json.dumps(extra_vars)]
        return preview_automation(
            server_id,
            tags,
            dry_run,
            {
                "playbook_name": playbook_name,
                "extra_vars_keys": sorted((extra_vars or {}).keys()),
            },
            argv,
        )
