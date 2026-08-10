"""Expose the indexed PDF query pipeline over HTTP.

Install:
    pip install "langchain>=1,<2" langchain-chroma langchain-openai \
        fastapi uvicorn

Start:
    export OPENAI_API_KEY="your-api-key"
    uvicorn query_api:app --reload

Query:
    curl -X POST http://127.0.0.1:8000/query \
        -H 'Content-Type: application/json' \
        -d '{"question":"How do I reset the Wi-Fi router?","k":4}'
"""

from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    k: int = Field(default=4, ge=1, le=20)


class Source(BaseModel):
    source: str
    page: int | str


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]


def format_documents(documents) -> str:
    return "\n\n".join(
        f"Source: {document.metadata.get('source', 'unknown')}\n"
        f"Page: {document.metadata.get('page', 'unknown')}\n"
        f"Content: {document.page_content}"
        for document in documents
    )


def get_vector_store() -> Chroma:
    default_chroma_db_path = os.path.join(tempfile.gettempdir(), "pdf_rag")
    db_dir = Path(os.getenv("CHROMA_DB_DIR", default_chroma_db_path))
    return Chroma(
        collection_name="pdf_documents",
        persist_directory=str(db_dir),
    )


def get_chain():
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
    model = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
    )
    return prompt | model | StrOutputParser()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # These objects are created once per worker process and shared by requests.
    app.state.vector_store = get_vector_store()
    app.state.chain = get_chain() if os.getenv("OPENAI_API_KEY") else None
    yield


app = FastAPI(title="PDF RAG API", version="1.0.0", lifespan=lifespan)


@app.post("/query", response_model=QueryResponse)
def query_documents(payload: QueryRequest, request: Request) -> QueryResponse:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")

    try:
        documents = request.app.state.vector_store.similarity_search(payload.question, k=payload.k)
        if not documents:
            return QueryResponse(answer="No matching document chunks were found.", sources=[])

        answer = request.app.state.chain.invoke(
            {
                "context": format_documents(documents),
                "question": payload.question,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    sources = [
        Source(
            source=str(document.metadata.get("source", "unknown")),
            page=document.metadata.get("page", "unknown"),
        )
        for document in documents
    ]
    return QueryResponse(answer=answer, sources=sources)
