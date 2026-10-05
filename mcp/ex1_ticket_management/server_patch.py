import ast
import json
import re
import shutil
import tempfile
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from models import PatchFileChange, SourceFile, SourceFileListing

mcp = FastMCP("Patch-Execution-Server", port=8003)

# Consolidate directory path under tempfile.gettempdir() / "mcp_ex1" / "src"
CODE_DIR = Path(tempfile.gettempdir()).joinpath("mcp_ex1", "src").resolve()
CODE_DIR.mkdir(parents=True, exist_ok=True)


@mcp.tool()
def reset_source_workspace(files: list[SourceFile]) -> dict:
    """Replaces the disposable workspace with bootstrap-provided files."""
    if not files:
        raise ValueError("At least one source file is required")

    prepared_files = []
    seen_paths = set()
    for source_file in files:
        path = _resolve_safe_path(
            source_file.filename,
            source_file.application_name,
            source_file.host_name,
        )
        if path in seen_paths:
            raise ValueError(f"Duplicate source file: {source_file.filename}")
        seen_paths.add(path)
        prepared_files.append((source_file, path))

    shutil.rmtree(CODE_DIR, ignore_errors=True)
    CODE_DIR.mkdir(parents=True)
    for source_file, path in prepared_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source_file.content, encoding="utf-8")
    return {
        "status": "reset",
        "files": [
            {
                "application_name": source_file.application_name,
                "host_name": source_file.host_name,
                "filename": path.relative_to(
                    _application_dir(
                        source_file.application_name,
                        source_file.host_name,
                    )
                ).as_posix(),
            }
            for source_file, path in prepared_files
        ],
    }


def _validate_context_name(value: str, label: str) -> str:
    normalized_value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", normalized_value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return normalized_value


def _application_dir(application_name: str, host_name: str) -> Path:
    safe_application = _validate_context_name(
        application_name,
        "application name",
    )
    safe_host = _validate_context_name(host_name or "localhost", "host name")
    application_dir = (CODE_DIR / safe_host / safe_application).resolve()
    try:
        application_dir.relative_to(CODE_DIR)
    except ValueError as exc:
        raise ValueError("Application workspace escapes source root") from exc
    return application_dir


def _resolve_safe_path(
    filename: str,
    application_name: str,
    host_name: str = "localhost",
) -> Path:
    application_dir = _application_dir(application_name, host_name)
    candidate = (application_dir / filename).resolve()
    try:
        candidate.relative_to(application_dir)
    except ValueError as exc:
        message = (
            "Security violation: Attempted write outside source directory."
        )
        raise ValueError(message) from exc
    return candidate


@mcp.tool()
def list_source_files(
    application_name: str,
    host_name: str = "localhost",
) -> SourceFileListing:
    """Lists source paths for one application on the requested host."""
    application_dir = _application_dir(application_name, host_name)
    filenames = []
    for path in sorted(application_dir.rglob("*")):
        if not path.is_file():
            continue
        filenames.append(path.relative_to(application_dir).as_posix())
    return SourceFileListing(
        application_name=application_name,
        host_name=host_name or "localhost",
        files=filenames,
    )


@mcp.tool()
def get_current_file(
    application_name: str,
    filename: str,
    host_name: str = "localhost",
) -> dict[str, str]:
    """Returns one file from an application on the requested host."""
    safe_path = _resolve_safe_path(filename, application_name, host_name)
    if not safe_path.is_file():
        raise FileNotFoundError(f"Source file does not exist: {filename}")
    content = safe_path.read_text(encoding="utf-8")
    return {
        "application_name": application_name,
        "host_name": host_name or "localhost",
        "filename": filename,
        "content": content,
    }


def _validate_file_changes(
    changes: list[PatchFileChange],
) -> list[tuple[PatchFileChange, Path, str | None]]:
    prepared_changes = []
    seen_paths = set()
    for change in changes:
        path = _resolve_safe_path(
            change.filename,
            change.application_name,
            change.host_name,
        )
        if path in seen_paths:
            raise ValueError(f"Duplicate file in patch: {change.filename}")
        seen_paths.add(path)

        exists = path.is_file()
        if change.operation == "create" and exists:
            raise ValueError(f"Cannot create existing file: {change.filename}")
        if change.operation in {"update", "delete"} and not exists:
            raise ValueError(
                f"Cannot {change.operation} missing file: {change.filename}"
            )
        original_content = path.read_text(encoding="utf-8") if exists else None
        if (
            change.operation == "update"
            and change.content == original_content
        ):
            raise ValueError(f"Patch does not change file: {change.filename}")
        _validate_content(path, change)
        prepared_changes.append((change, path, original_content))
    return prepared_changes


def _validate_content(path: Path, change: PatchFileChange) -> None:
    if change.operation == "delete":
        return

    content = change.content or ""
    if not content.strip():
        raise ValueError(f"Patch content is empty: {change.filename}")
    lowered_content = content.lower()
    if (
        "placeholder" in lowered_content
        or "[date of incident]" in lowered_content
    ):
        raise ValueError(f"Patch contains placeholder text: {change.filename}")
    if path.suffix == ".py":
        try:
            ast.parse(content, filename=change.filename)
        except SyntaxError as exc:
            raise ValueError(
                f"Invalid Python syntax in {change.filename}: {exc}"
            ) from exc
    elif path.suffix == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in {change.filename}: {exc}"
            ) from exc


def _restore_file_changes(
    prepared_changes: list[tuple[PatchFileChange, Path, str | None]],
) -> list[str]:
    rollback_errors = []
    for _, path, original_content in reversed(prepared_changes):
        try:
            if original_content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(original_content, encoding="utf-8")
        except OSError as exc:
            rollback_errors.append(f"{path.name}: {exc}")
    return rollback_errors


@mcp.tool()
def apply_file_changes(changes: list[PatchFileChange]) -> dict:
    """Applies a validated set of file creations, updates, and deletions."""
    if not changes:
        return {"status": "failure", "error_message": "Patch has no changes"}

    try:
        prepared_changes = _validate_file_changes(changes)
    except (OSError, ValueError) as exc:
        return {"status": "failure", "error_message": str(exc)}

    try:
        for change, path, _ in prepared_changes:
            if change.operation == "delete":
                path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(change.content or "", encoding="utf-8")
    except OSError as exc:
        rollback_errors = _restore_file_changes(prepared_changes)
        error_message = str(exc)
        if rollback_errors:
            error_message += "; rollback errors: " + ", ".join(rollback_errors)
        return {"status": "failure", "error_message": error_message}

    return {
        "status": "applied",
        "files": [
            {
                "application_name": change.application_name,
                "host_name": change.host_name,
                "filename": change.filename,
                "operation": change.operation,
            }
            for change, _, _ in prepared_changes
        ],
    }


if __name__ == "__main__":
    print(f"Patch workspace initialized at: {CODE_DIR}")
    print("Starting Server 3 (Patch Execution) on port 8003...")
    mcp.run(transport="sse")
