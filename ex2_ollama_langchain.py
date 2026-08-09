from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="qwen3:1.7b",
    base_url="http://localhost:11434",
    temperature=0
)

response = llm.invoke("Explain Apache Spark in one paragraph.")
print(response.content)