import re
from .core import *

UNIT_RE = re.compile(
    r"^[A-Za-z0-9_.@+\-]+(?:\.(?:service|socket|timer|target|mount|path|slice))?$"
)


def normalize_unit(service: str) -> str:
    if not service or not UNIT_RE.match(service):
        raise GatewayError(
            "INVALID_SERVICE",
            "service_name must be a unit name (letters, digits, and . _ @ + -)",
        )
    return service if "." in service else service + ".service"


def service_call(settings, sid, tags, service, action, privileged=False):
    unit = normalize_unit(service)
    return read_only(
        settings,
        sid,
        tags,
        lambda n: {
            "raw": run_ssh(
                settings,
                n,
                ["/usr/bin/systemctl", action, unit],
                privileged=privileged,
            )
        },
    )


def list_services_call(settings, sid, tags):
    return read_only(
        settings,
        sid,
        tags,
        lambda n: {
            "raw": run_ssh(
                settings,
                n,
                [
                    "/usr/bin/systemctl",
                    "list-unit-files",
                    "--type=service",
                    "--no-legend",
                    "--no-pager",
                ],
            )
        },
    )


def register(mcp, settings):
    for name, action, doc in [
        (
            "list_systemd_services",
            "list-unit-files",
            "List installed systemd service units.",
        ),
        (
            "systemd_service_exists",
            "list-unit-files",
            "Check whether a systemd unit exists.",
        ),
        ("get_service_status", "status", "Get systemd service status."),
    ]:

        def tool(
            server_id: str | None = None,
            tags: list[str] | None = None,
            service_name: str = "",
            _action=action,
            _name=name,
        ):
            if _name == "list_systemd_services":
                return list_services_call(settings, server_id, tags)
            return service_call(settings, server_id, tags, service_name, _action)

        tool.__name__ = name
        tool.__doc__ = doc
        mcp.tool(exclude_args=["_action", "_name"])(tool)
    for name, action, doc in [
        ("start_systemd_service", "start", "Start a systemd service."),
        ("stop_systemd_service", "stop", "Stop a systemd service."),
        ("restart_systemd_service", "restart", "Restart a systemd service."),
        ("reload_systemd_service", "reload", "Reload a systemd service."),
    ]:

        def mutate(
            server_id: str | None = None,
            tags: list[str] | None = None,
            service_name: str = "",
            dry_run: bool = True,
            _action=action,
            _name=name,
        ):
            unit = normalize_unit(service_name)
            if dry_run:
                return envelope(
                    "dry_run_preview",
                    "single" if server_id else "multi_tag",
                    server_id=server_id,
                    dry_run=True,
                    data={"action": _action, "service_name": unit},
                )
            return service_call(
                settings, server_id, tags, unit, _action, privileged=True
            )

        mutate.__name__ = name
        mutate.__doc__ = doc
        mcp.tool(exclude_args=["_action", "_name"])(mutate)

    @mcp.tool()
    def remove_systemd_service(
        server_id: str | None = None,
        tags: list[str] | None = None,
        service_name: str = "",
        dry_run: bool = True,
    ) -> dict:
        """Preview removal (stop, disable, delete unit) of a systemd service; active removal requires a privileged wrapper."""
        unit = normalize_unit(service_name)
        if not dry_run:
            raise GatewayError(
                "MUTATION_DISABLED",
                "service removal requires an approved privileged wrapper",
            )
        return envelope(
            "dry_run_preview",
            "single" if server_id else "multi_tag",
            server_id=server_id,
            dry_run=True,
            data={
                "action": "remove",
                "service_name": unit,
                "planned_steps": ["stop", "disable", "delete unit file", "daemon-reload"],
            },
        )

    @mcp.tool()
    def add_systemd_service(
        server_id: str | None = None,
        tags: list[str] | None = None,
        service_name: str = "",
        unit_content: str = "",
        enable_on_boot: bool = True,
        dry_run: bool = True,
    ) -> dict:
        """Preview creation of a systemd unit; active writes require a privileged wrapper."""
        unit = normalize_unit(service_name)
        if dry_run:
            return envelope(
                "dry_run_preview",
                "single" if server_id else "multi_tag",
                server_id=server_id,
                dry_run=True,
                data={"service_name": unit, "enable_on_boot": enable_on_boot},
            )
        raise GatewayError(
            "MUTATION_DISABLED",
            "systemd unit writes require an approved privileged wrapper",
        )
