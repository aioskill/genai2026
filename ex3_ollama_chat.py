from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

llm = ChatOllama(
    model="qwen3:1.7b",
    base_url="http://localhost:11434"
)

response = llm.invoke([
    HumanMessage(content="What is LangChain?")
])

print(response.content)