from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


APP_NAME = "Local File System Demo"
DEFAULT_ROOT = Path.cwd() / "demo_workspace"

mcp = FastMCP(
    APP_NAME,
    instructions="Use only paths inside the configured demo workspace.",
)


def workspace_root() -> Path:
    root = Path(os.environ.get("MCP_FS_ROOT", DEFAULT_ROOT)).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_path(relative_path: str) -> Path:
    root = workspace_root()
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ValueError("absolute paths are not allowed")

    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("path escapes the demo workspace")

    return resolved


def describe_entry(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path.relative_to(workspace_root())),
        "kind": "directory" if path.is_dir() else "file",
        "size": stat.st_size,
        "modified": stat.st_mtime,
    }


@mcp.tool()
def list_directory(path: str = ".") -> list[dict[str, Any]]:
    """List files and folders under a path inside the demo workspace."""

    directory = resolve_path(path)
    if not directory.exists():
        raise FileNotFoundError(f"{path!r} does not exist")
    if not directory.is_dir():
        raise NotADirectoryError(f"{path!r} is not a directory")

    entries = [describe_entry(item) for item in sorted(directory.iterdir(), key=lambda p: p.name.lower())]
    return entries


@mcp.tool()
def read_text_file(path: str) -> str:
    """Read a text file from the demo workspace."""

    file_path = resolve_path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"{path!r} does not exist")
    if not file_path.is_file():
        raise IsADirectoryError(f"{path!r} is not a file")

    return file_path.read_text(encoding="utf-8")


@mcp.tool()
def write_text_file(path: str, content: str) -> str:
    """Write a text file inside the demo workspace."""

    file_path = resolve_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return f"wrote {file_path.relative_to(workspace_root())}"


@mcp.tool()
def make_directory(path: str) -> str:
    """Create a directory inside the demo workspace."""

    directory = resolve_path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return f"created {directory.relative_to(workspace_root())}"


@mcp.resource("resource://briefing")
def briefing_resource() -> str:
    """Expose the synthesized briefing as an MCP resource."""

    briefing_path = resolve_path("briefing.txt")
    if not briefing_path.exists():
        return "Briefing not generated yet."
    return briefing_path.read_text(encoding="utf-8")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
