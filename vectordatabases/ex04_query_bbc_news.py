"""Query the persisted BBC News Summary Chroma collection."""

from __future__ import annotations

import argparse
from pathlib import Path

import chromadb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_DIR = PROJECT_ROOT / "tmp" / "bbc_news_chroma_db"
DEFAULT_COLLECTION_NAME = "bbc_news_summary"
DEFAULT_RESULT_COUNT = 5


def build_metadata_filter(
    source_type: str | None,
    category: str | None,
) -> dict[str, str] | None:
    """Build a Chroma metadata filter from optional CLI values."""
    metadata_filter = {}
    if source_type:
        metadata_filter["source_type"] = source_type
    if category:
        metadata_filter["category"] = category
    return metadata_filter or None


def query_collection(
    question: str,
    database_dir: Path,
    collection_name: str,
    result_count: int,
    metadata_filter: dict[str, str] | None,
) -> dict:
    """Run a similarity query against the persisted collection."""
    client = chromadb.PersistentClient(path=str(database_dir))
    collection = client.get_collection(name=collection_name)
    return collection.query(
        query_texts=[question],
        n_results=result_count,
        where=metadata_filter,
        include=["documents", "metadatas", "distances"],
    )


def print_results(results: dict) -> None:
    """Print query matches in a readable format."""
    result_ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for index, result_id in enumerate(result_ids, start=1):
        print(f"\n--- Result {index}: {result_id} ---")
        print(f"Distance: {distances[index - 1]}")
        print(f"Metadata: {metadatas[index - 1]}")
        print(documents[index - 1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="Natural-language question to search for")
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
        "--n-results",
        type=int,
        default=DEFAULT_RESULT_COUNT,
        help=f"Number of matches to return (default: {DEFAULT_RESULT_COUNT})",
    )
    parser.add_argument(
        "--source-type",
        help="Filter by source type, for example 'News Articles' or 'Summaries'",
    )
    parser.add_argument("--category", help="Filter by category, for example 'business'")
    args = parser.parse_args()

    if args.n_results < 1:
        parser.error("--n-results must be greater than zero")

    metadata_filter = build_metadata_filter(args.source_type, args.category)
    results = query_collection(
        question=args.question,
        database_dir=args.db_dir,
        collection_name=args.collection,
        result_count=args.n_results,
        metadata_filter=metadata_filter,
    )
    print_results(results)


if __name__ == "__main__":
    main()
