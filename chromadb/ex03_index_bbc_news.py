"""Index the BBC News Summary dataset in a persistent Chroma collection.

Each text file is stored as one document.  The default Chroma embedding
function is used, so the first run may download its local embedding model.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import chromadb
import chromadb.errors
from pydantic import BaseModel
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATASET_DIR = Path(os.environ['DATA_DIR']) / "BBC News Summary"
DEFAULT_DATABASE_DIR = Path(os.environ['TMP_DIR']) / "bbc_news_chroma_db"
DEFAULT_COLLECTION_NAME = "bbc_news_summary"
DEFAULT_BATCH_SIZE = 100


class IndexedDocument(BaseModel):
    """One dataset record prepared for insertion into Chroma."""

    id: str
    document: str
    metadata: dict[str, str]


def read_documents(dataset_dir: Path) -> list[IndexedDocument]:
    """Read dataset text files and return one model per document."""
    files = sorted(dataset_dir.rglob("*.txt"))
    if not files:
        raise FileNotFoundError(f"No .txt files found under {dataset_dir}")

    records: list[IndexedDocument] = []

    for path in files:
        relative_path = path.relative_to(dataset_dir)
        parts = relative_path.parts
        if len(parts) < 3:
            raise ValueError(
                f"Expected files below '<source>/<category>/', got {relative_path}"
            )

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Some copies of this dataset contain legacy Windows-1252 bytes.
            text = path.read_text(encoding="cp1252")

        records.append(
            IndexedDocument(
                id=relative_path.as_posix(),
                document=text,
                metadata={
                    "source_type": parts[0],
                    "category": parts[1],
                    "filename": path.name,
                    "source": relative_path.as_posix(),
                },
            )
        )

    return records


def index_dataset(
    dataset_dir: Path,
    database_dir: Path,
    collection_name: str,
    batch_size: int,
    rebuild: bool = False,
) -> int:
    """Create or update the Chroma collection and return its document count."""
    records = read_documents(dataset_dir)
    client = chromadb.PersistentClient(path=str(database_dir))

    if rebuild:
        try:
            if client.get_collection(name=collection_name):
                client.delete_collection(name=collection_name)
                print(f"Dropped existing collection: {collection_name}")
        except chromadb.errors.NotFoundError:
            # The collection does not exist yet, so there is nothing to rebuild.
            pass

    collection = client.get_or_create_collection(name=collection_name)

    batch_starts = range(0, len(records), batch_size)
    for start in tqdm(batch_starts, desc="Indexing BBC News", unit="batch"):
        batch = records[start : start + batch_size]
        collection.upsert(
            ids=[record.id for record in batch],
            documents=[record.document for record in batch],
            metadatas=[record.metadata for record in batch],
        )

    return collection.count()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help=f"Dataset directory (default: {DEFAULT_DATASET_DIR})",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=DEFAULT_DATABASE_DIR,
        help=f"Persistent Chroma directory (default: {DEFAULT_DATABASE_DIR})",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION_NAME,
        help=f"Chroma collection name (default: {DEFAULT_COLLECTION_NAME})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of documents written per batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete and recreate the collection before indexing",
    )
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size must be greater than zero")

    count = index_dataset(
        dataset_dir=args.data_dir,
        database_dir=args.db_dir,
        collection_name=args.collection,
        batch_size=args.batch_size,
        rebuild=args.rebuild,
    )
    print(f"Indexed {count} documents in collection '{args.collection}' at {args.db_dir}")


if __name__ == "__main__":
    main()
