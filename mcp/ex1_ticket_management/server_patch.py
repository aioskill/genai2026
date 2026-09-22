import tempfile
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Patch-Execution-Server", port=8003)

# Consolidate directory path under tempfile.gettempdir() / "mcp_ex1" / "src"
CODE_DIR = Path(tempfile.gettempdir()).joinpath("mcp_ex1", "src").resolve()
CODE_DIR.mkdir(parents=True, exist_ok=True)

# Pre-populate sample broken config file
with open(CODE_DIR / "db_config.json", "w", encoding="utf-8") as f:
    f.write('{\n  "connection_timeout_ms": 1000\n}')


def _resolve_safe_path(filename: str) -> Path:
    candidate = (CODE_DIR / filename).resolve()
    try:
        candidate.relative_to(CODE_DIR)
    except ValueError as exc:
        raise ValueError("Security violation: Attempted write outside source directory.") from exc
    return candidate


@mcp.tool()
def apply_code_patch(filename: str, patch_content: str) -> str:
    """
    SENSITIVE TOOL: Writes patch content directly to local project source files.
    Requires explicit Human-In-The-Loop (HITL) authorization on the client side!
    """
    safe_path = _resolve_safe_path(filename)

    with open(safe_path, "w", encoding="utf-8") as f:
        f.write(patch_content)

    return f"Successfully applied patch to {filename} at path: {safe_path}"


if __name__ == "__main__":
    print(f"Patch workspace initialized at: {CODE_DIR}")
    print("Starting Server 3 (Patch Execution) on port 8003...")
    mcp.run(transport="sse")
