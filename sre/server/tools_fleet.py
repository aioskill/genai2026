from .core import *


def register(mcp, settings):
    @mcp.tool()
    def list_managed_servers() -> dict:
        """List enabled servers, addresses, tags, and declared platforms."""
        return {
            "status": "success",
            "target_type": "fleet",
            "dry_run": False,
            "data": {"servers": [asdict(n) for n in settings.servers.values()]},
        }

    @mcp.tool()
    def get_system_health(
        server_id: str | None = None, tags: list[str] | None = None
    ) -> dict:
        """Retrieve load, memory, swap, and uptime metrics."""
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {"raw": run_ssh(settings, n, ["/usr/bin/uptime"])},
        )

    @mcp.tool()
    def get_disk_usage(
        server_id: str | None = None,
        tags: list[str] | None = None,
        mount_point: str = "/",
    ) -> dict:
        """Retrieve filesystem and inode utilization for a mount point."""
        if not mount_point.startswith("/"):
            raise GatewayError("INVALID_PATH", "mount_point must be absolute")
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {
                "raw": run_ssh(
                    settings, n, ["/usr/bin/df", "-P", "-i", "--", mount_point]
                )
            },
        )
