from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

prompt = ChatPromptTemplate.from_template(
    "You are a data engineering expert.\nQuestion: {question}"
)

llm = ChatOllama(model="qwen3:1.7b")

chain = prompt | llm

response = chain.invoke({
    "question": "What is Apache Iceberg?"
})

print(response.content)