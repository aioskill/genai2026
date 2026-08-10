from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma

embeddings = OllamaEmbeddings(model="nomic-embed-text")
db = Chroma(
    persist_directory="/tmp/chroma_db",
    embedding_function=embeddings
)

retriever = db.as_retriever()
docs = retriever.invoke("What is Delta Lake?")
llm = ChatOllama(model="qwen3:1.7b")
context = "\n".join([d.page_content for d in docs])

response = llm.invoke(
    f"Answer using only the following context:\n\n{context}"
)

print(response.content)