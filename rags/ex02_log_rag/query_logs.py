"""Query log entries indexed by index_logs.py to find root cause of failures.

Install:
    pip install "langchain>=1,<2" langchain-chroma langchain-openai

Example:
    export OPENAI_API_KEY="your-api-key"
    python query_logs.py --db-dir ./chroma_db \
        --question "What caused the OutOfMemoryError and what should be done?"
"""

from __future__ import annotations
from dotenv import load_dotenv
import argparse
import os
import tempfile
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

def format_documents(documents) -> str:
    """Format retrieved log entries so the model can reason over them."""
    return "\n\n".join(
        f"Timestamp: {document.metadata.get('timestamp', 'unknown')}\n"
        f"Level: {document.metadata.get('level', 'unknown')}\n"
        f"Component: {document.metadata.get('component', 'unknown')}\n"
        f"Source: {document.metadata.get('source', 'unknown')}\n"
        f"Message: {document.page_content}"
        for document in documents
    )


def main() -> None:
    default_chroma_db_path = os.path.join(tempfile.gettempdir(), "ex02_log_rag")
    parser = argparse.ArgumentParser(
        description="Query indexed log entries to find the root cause"
    )
    parser.add_argument("--db-dir", type=Path, default=Path(default_chroma_db_path))
    parser.add_argument("--question", required=True)
    parser.add_argument("--k", type=int, default=8, help="Number of log entries to retrieve")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY before running this script")

    # Do not pass an embedding function here. This matches index_logs.py and
    # lets Chroma use its default encoder for the query as well.
    vector_store = Chroma(
        collection_name="log_entries",
        persist_directory=str(args.db_dir),
    )
    documents = vector_store.similarity_search(args.question, k=args.k)
    if not documents:
        print("No matching log entries were found.")
        return

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an SRE performing root cause analysis from log entries.\n"
                "Analyze the supplied log entries in chronological order and:\n"
                "1. Identify the root cause of the incident\n"
                "2. List the evidence (timestamps, levels, components) that supports it\n"
                "3. Suggest concrete remediation or next steps\n"
                "If the evidence is insufficient, say so instead of guessing.\n\n"
                "Log entries:\n{context}",
            ),
            ("human", "{question}"),
        ]
    )
    chain = prompt | ChatOpenAI(model=args.model, temperature=0) | StrOutputParser()
    answer = chain.invoke(
        {"context": format_documents(documents), "question": args.question}
    )

    print(f"Answer:\n{answer}\n")
    print("Sources:")
    sources = {
        document.metadata.get("source", "unknown") for document in documents
    }
    for source in sorted(sources):
        print(f"- {source}")


if __name__ == "__main__":
    main()
