"""Query PDF chunks stored by index_pdfs.py using an OpenAI chat model.

Install:
    pip install "langchain>=1,<2" langchain-chroma langchain-openai

Example:
    export OPENAI_API_KEY="your-api-key"
    python query_docs.py --db-dir ./chroma_db \
        --question "What is the main topic of these documents?"
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
    """Format retrieved chunks so the model can cite their source files."""
    return "\n\n".join(
        f"Source: {document.metadata.get('source', 'unknown')}\n"
        f"Page: {document.metadata.get('page', 'unknown')}\n"
        f"Content: {document.page_content}"
        for document in documents
    )


def main() -> None:
    # Example questions:
    # "How do I reset the Wi-Fi router?"
    # "What is ratio of coffee and water for making a strong cup?"
    # "How do I replace the filter in the SmartAir Purifier X1?"
    # "What security best practices does the SecureHome router manual recommend?"
    # "Give the recommended coffee-to-water ratio for the AquaBrew CM-200."
    # "How do I remove limescale from the ThermoKettle Pro TK-1?"

    default_chroma_db_path = os.path.join(tempfile.gettempdir(), "pdf_rag")
    parser = argparse.ArgumentParser(description="Query indexed PDF documents")
    parser.add_argument("--db-dir", type=Path, default=Path(default_chroma_db_path))
    parser.add_argument("--question", required=True)
    parser.add_argument("--k", type=int, default=4, help="Number of chunks to retrieve")
    parser.add_argument("--model", default=os.environ['OPENAI_MODEL'])
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY before running this script")

    # Do not pass an embedding function here. This matches index_pdfs.py and
    # lets Chroma use its default encoder for the query as well.
    vector_store = Chroma(
        collection_name="pdf_documents",
        persist_directory=str(args.db_dir),
    )
    documents = vector_store.similarity_search(args.question, k=args.k)
    if not documents:
        print("No matching document chunks were found.")
        return

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Answer only from the supplied context. If the answer is not "
                "in the context, say you do not know.\n\nContext:\n{context}",
            ),
            ("human", "{question}"),
        ]
    )
    chain = prompt | ChatOpenAI(model=args.model, temperature=0) | StrOutputParser()
    answer = chain.invoke(
        {"context": format_documents(documents), "question": args.question}
    )

    print(f"Answer:\n{answer}\n")
    print("Retrieved sources:")
    for document in documents:
        print(
            f"- {document.metadata.get('source', 'unknown')} "
            f"(page {document.metadata.get('page', 'unknown')})"
        )


if __name__ == "__main__":
    main()
