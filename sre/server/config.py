from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import os
import yaml


@dataclass
class Server:
    id: str
    host: str
    port: int = 22
    tags: list[str] = field(default_factory=list)
    platform: str | None = None
    enabled: bool = True


@dataclass
class Settings:
    raw: dict[str, Any]
    servers: dict[str, Server]
    config_path: Path
    approved_paths: dict[str, dict] = field(default_factory=dict)

    @property
    def gateway(self) -> dict[str, Any]:
        return self.raw.get("gateway", {})

    @property
    def ssh(self) -> dict[str, Any]:
        return self.raw.get("ssh", {})

    @property
    def scheduler(self) -> dict[str, Any]:
        return self.raw.get("task_scheduler", {})

    @property
    def allowed_roots(self) -> list[str]:
        return self.gateway.get(
            "allowed_roots", ["/var/log", "/etc", "/opt", "/srv", "/tmp"]
        )


def load_settings(path: str | Path | None = None) -> Settings:
    selected = Path(
        path or os.getenv("SRE_CONFIG", Path(__file__).with_name("config.yaml"))
    ).expanduser()
    raw = yaml.safe_load(selected.read_text()) or {}
    inventory = raw.get("fleet_inventory", {}).get("servers", [])
    servers = {
        item["id"]: Server(
            **{k: item[k] for k in ("id", "host")},
            port=item.get("port", 22),
            tags=item.get("tags", []),
            platform=item.get("platform"),
            enabled=item.get("enabled", True),
        )
        for item in inventory
    }
    return Settings(raw=raw, servers=servers, config_path=selected)
