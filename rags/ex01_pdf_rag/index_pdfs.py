"""Read PDF files from a directory and index them in a persistent Chroma DB.

Install:
    pip install "langchain>=1,<2" langchain-chroma langchain-text-splitters pypdf

Example:
    python index_pdfs.py --pdf-dir ./pdfs --db-dir ./chroma_db
"""

from __future__ import annotations
import tempfile
import argparse
import hashlib
from pathlib import Path
import os.path
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


def stable_id(pdf_path: Path, page: int, chunk_number: int, text: str) -> str:
    """Return the same ID whenever the same PDF chunk is indexed again."""
    value = f"{pdf_path.resolve()}:{page}:{chunk_number}:{text}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_pdf(pdf_path: Path) -> list[Document]:
    print(f"Loading PDF: {pdf_path}")
    reader = PyPDFLoader(str(pdf_path))
    return [
        Document(
            page_content=page.page_content or "",
            metadata={"source": str(pdf_path), "page": page_number},
        )
        for page_number, page in enumerate(reader.load())
    ]


def index_pdfs(pdf_dir: Path, db_dir: Path) -> int:
    pdf_paths = sorted(pdf_dir.rglob("*.pdf"))
    if not pdf_paths:
        raise FileNotFoundError(f"No PDF files found below {pdf_dir.resolve()}")

    print("DB directory: ", db_dir)

    vector_store = Chroma(
        collection_name="pdf_documents",
        persist_directory=str(db_dir),
    )

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    documents = []
    ids = []

    for pdf_path in pdf_paths:
        pages = load_pdf(pdf_path)
        chunks = splitter.split_documents(pages)

        for chunk_number, document in enumerate(chunks):
            # Keep the path relative to the input directory in the metadata.
            document.metadata["source"] = str(pdf_path.relative_to(pdf_dir))
            document.metadata["file_name"] = pdf_path.name
            page = int(document.metadata.get("page", 0))
            documents.append(document)
            ids.append(stable_id(pdf_path, page, chunk_number, document.page_content))

    # Chroma persists automatically when persist_directory is configured.
    # Stable IDs make rerunning this script update the same chunks instead of
    # creating a new copy of every chunk.
    vector_store.add_documents(documents=documents, ids=ids)
    return len(documents)


def main() -> None:
    default_chroma_db_path = os.path.join(tempfile.gettempdir(), "ex01_pdf_rag")
    parser = argparse.ArgumentParser(description="Index PDFs into Chroma")
    parser.add_argument("--pdf-dir", type=Path, required=True)
    parser.add_argument("--db-dir", type=Path, default=Path(default_chroma_db_path))
    args = parser.parse_args()

    count = index_pdfs(args.pdf_dir, args.db_dir)
    print(f"Indexed {count} chunks into {args.db_dir.resolve()}")


if __name__ == "__main__":
    main()
