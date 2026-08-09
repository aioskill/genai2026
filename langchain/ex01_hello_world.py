import os

from langchain_openai import ChatOpenAI
# from langchain_deepseek import ChatDeepSeek
# from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

OPENAI_MODEL = os.environ["OPENAI_MODEL"]

prompt = ChatPromptTemplate.from_template(
    "Explain: {text}. Show raw texts in bullets. Keep output text short")
model = ChatOpenAI(model=OPENAI_MODEL, max_tokens = 1024)

# This expression is called LCEL (LangChain Expression Language)
chain = prompt | model
response = chain.invoke({"text": "langchain"})

# Plain Text Output
print(response.content)

# Extract Tool Calls (if functions/tools were bound)
if response.tool_calls:
    for tool_call in response.tool_calls:
        print("Tool Name:", tool_call["name"])
        print("Arguments:", tool_call["args"])

# Token Usage Metadata
if response.usage_metadata:
    print("Prompt Tokens:", response.usage_metadata["input_tokens"])
    print("Completion Tokens:", response.usage_metadata["output_tokens"])
print("Finish Reason:", response.response_metadata.get("finish_reason"))
