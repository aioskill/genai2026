from .core import *


def register(mcp, settings):
    @mcp.tool()
    def scan_vulnerabilities(
        server_id: str | None = None,
        tags: list[str] | None = None,
        severity_threshold: str = "medium",
    ) -> dict:
        """Run a read-only package security check."""
        if severity_threshold not in {"low", "medium", "high", "critical"}:
            raise GatewayError("INVALID_ARGUMENT", "invalid severity")
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {
                "raw": run_ssh(settings, n, ["/usr/bin/apt-get", "-s", "upgrade"])
            },
        )

    @mcp.tool()
    def check_cve_status(
        server_id: str | None = None, tags: list[str] | None = None, cve_id: str = ""
    ) -> dict:
        """Return package metadata for a CVE; external advisory correlation is deployment-specific."""
        if not cve_id.startswith("CVE-"):
            raise GatewayError("INVALID_CVE", "cve_id must start with CVE-")
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {
                "cve_id": cve_id,
                "status": "not_correlated",
                "raw": run_ssh(settings, n, ["/usr/bin/apt-get", "-s", "upgrade"]),
            },
        )

    @mcp.tool()
    def check_reboot_required(
        server_id: str | None = None, tags: list[str] | None = None
    ) -> dict:
        """Check whether the host reports a reboot requirement."""
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {
                "required": bool(
                    run_ssh(
                        settings, n, ["/usr/bin/test", "-f", "/var/run/reboot-required"]
                    )
                )
            },
        )

    @mcp.tool()
    def patch_cve(
        server_id: str | None = None,
        tags: list[str] | None = None,
        cve_id: str = "",
        dry_run: bool = True,
    ) -> dict:
        """Apply available package updates to remediate a CVE."""
        if not cve_id.startswith("CVE-"):
            raise GatewayError("INVALID_CVE", "cve_id must start with CVE-")
        if dry_run:
            return envelope(
                "dry_run_preview",
                "single" if server_id else "multi_tag",
                server_id=server_id,
                dry_run=True,
                data={"cve_id": cve_id},
            )
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: {
                "cve_id": cve_id,
                "raw": run_ssh(
                    settings,
                    n,
                    [
                        "/usr/bin/apt-get",
                        "-y",
                        "-o",
                        "Dpkg::Options::=--force-confold",
                        "upgrade",
                    ],
                    privileged=True,
                ),
            },
        )
