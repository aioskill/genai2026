from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
import tempfile
from dotenv import load_dotenv
import os.path

load_dotenv()

CHROMA_PATH = os.path.join(tempfile.gettempdir(), "chromadb")


# Initialize embedding model and vector store
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vector_store = Chroma(
    collection_name="rag_docs",
    embedding_function=embeddings,
    persist_directory=CHROMA_PATH,
    collection_metadata={"hnsw:space": "cosine"},
)

# Add documents
docs = [
    Document(
        page_content="ChromaDB stores vector embeddings",
        metadata={"source": "doc1"},
        id = "doc1"
    ),
    Document(
        page_content="LangChain simplifies LLM application development",
        metadata={"source": "doc2"},
        id = "doc2"
    ),
]
vector_store.add_documents(docs)

# Similarity search
results = vector_store.similarity_search("vector database", k=2)
for doc in results:
    print(doc.page_content)

print("#"*100)
results = vector_store.similarity_search_with_score("vector database", k=2)
for doc in results:
    print(doc)