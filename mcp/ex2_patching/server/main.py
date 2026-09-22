from __future__ import annotations
import argparse, logging
from .logging_config import configure_logging
from .safe_mcp import SafeFastMCP
from .config import load_settings
from . import (
    tools_fleet,
    tools_files,
    tools_config,
    tools_systemd,
    tools_users,
    tools_security,
    tools_automation,
)


def create_server(config_path=None):
    settings = load_settings(config_path)
    mcp = SafeFastMCP(settings.gateway.get("id", "linux-sre-mcp-gateway"))
    for module in (
        tools_fleet,
        tools_files,
        tools_config,
        tools_systemd,
        tools_users,
        tools_security,
        tools_automation,
    ):
        module.register(mcp, settings)
    return mcp


def main():
    parser = argparse.ArgumentParser(description="Linux SRE MCP Gateway")
    parser.add_argument(
        "--config", help="YAML configuration path; defaults to server/config.yaml"
    )
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument(
        "--host", help="HTTP host override; otherwise gateway.host is used"
    )
    parser.add_argument(
        "--port", type=int, help="HTTP port override; otherwise gateway.port is used"
    )
    args = parser.parse_args()
    settings = load_settings(args.config)
    if args.log_level != "INFO":
        settings.raw.setdefault("gateway", {})["log_level"] = args.log_level
    configure_logging(settings)

    server = create_server(args.config)
    host = args.host or settings.gateway.get("host", "127.0.0.1")
    port = args.port or int(settings.gateway.get("port", 8000))
    server.run(transport="sse", host=host, port=port)


if __name__ == "__main__":
    main()
