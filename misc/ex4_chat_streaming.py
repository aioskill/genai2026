from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="qwen3:1.7b",
    base_url="http://localhost:11434"
)

for chunk in llm.stream("Tell me a joke"):
    print(chunk.content, end="", flush=True)