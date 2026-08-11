"""Read log files from a directory and index them in a persistent Chroma DB.

Each log line becomes one chunk. The structured fields (timestamp, level,
component, message and key=value pairs) are stored in the document metadata so
queries can filter or present them.

Install:
    pip install "langchain>=1,<2" langchain-chroma

Example:
    python index_logs.py --log-dir ./logs --db-dir ./chroma_db
"""

from __future__ import annotations
import tempfile
import argparse
import hashlib
import re
from pathlib import Path
import os.path
from langchain_chroma import Chroma
from langchain_core.documents import Document


# Matches lines like:
#   2025-02-01 11:20:01 INFO AppServer Service started version=3.4.1
LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>\w+)\s+"
    r"(?P<component>\S+)\s+"
    r"(?P<message>.*)$"
)

# Matches trailing key=value tokens, e.g. "version=3.4.1" or "query_time=3200ms".
KV_PATTERN = re.compile(r"(\w+)=([^\s]+)")


def stable_id(log_path: Path, line_number: int, text: str) -> str:
    """Return the same ID whenever the same log line is indexed again."""
    value = f"{log_path.resolve()}:{line_number}:{text}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_log_line(line_number: int, line: str) -> tuple[dict, str, str] | None:
    """Parse one log line into (metadata, page_content, id) or None if malformed."""
    match = LOG_LINE_PATTERN.match(line)
    if not match:
        return None

    groups = match.groupdict()
    message = groups["message"]
    kv_pairs = dict(KV_PATTERN.findall(message))
    # Keep the plain-text message, stripping any key=value tokens.
    plain_message = KV_PATTERN.sub("", message).strip()

    metadata = {
        "timestamp": groups["timestamp"],
        "level": groups["level"],
        "component": groups["component"],
        "message": plain_message,
    }
    metadata.update(kv_pairs)

    page_content = line.rstrip("\n")
    return metadata, page_content, f"{groups['timestamp']} {groups['level']} {groups['component']} {plain_message}"


def load_log_file(log_path: Path) -> list[Document]:
    print(f"Loading log: {log_path}")
    documents = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            parsed = parse_log_line(line_number, line)
            if parsed is None:
                continue
            metadata, page_content, text = parsed
            metadata["source"] = str(log_path)
            metadata["file_name"] = log_path.name
            documents.append(Document(page_content=page_content, metadata=metadata))
    return documents


def index_logs(log_dir: Path, db_dir: Path) -> int:
    log_paths = sorted(log_dir.rglob("*.log"))
    if not log_paths:
        raise FileNotFoundError(f"No .log files found below {log_dir.resolve()}")

    print("DB directory: ", db_dir)

    vector_store = Chroma(
        collection_name="log_entries",
        persist_directory=str(db_dir),
    )

    documents = []
    ids = []

    for log_path in log_paths:
        for line_number, document in enumerate(load_log_file(log_path), start=1):
            # Keep the path relative to the input directory in the metadata.
            document.metadata["source"] = str(log_path.relative_to(log_dir))
            documents.append(document)
            ids.append(stable_id(log_path, line_number, document.page_content))

    # Chroma persists automatically when persist_directory is configured.
    # Stable IDs make rerunning this script update the same entries instead of
    # creating a new copy of every line.
    vector_store.add_documents(documents=documents, ids=ids)
    return len(documents)


def main() -> None:
    default_chroma_db_path = os.path.join(tempfile.gettempdir(), "ex02_log_rag")
    parser = argparse.ArgumentParser(description="Index log files into Chroma")
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument("--db-dir", type=Path, default=Path(default_chroma_db_path))
    args = parser.parse_args()

    count = index_logs(args.log_dir, args.db_dir)
    print(f"Indexed {count} log entries into {args.db_dir.resolve()}")


if __name__ == "__main__":
    main()
