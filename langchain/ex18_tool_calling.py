import os
from pprint import pprint

from langchain_core.tools import tool
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from dotenv import load_dotenv
from typing import Union, List, Dict
from pydantic import BaseModel
load_dotenv()


class LLMTraceHandler(BaseCallbackHandler):
    """Print the exact messages sent to, and raw responses from, the LLM."""

    def on_chat_model_start(self, serialized, messages, **kwargs):
        print("\n--- Prompt sent to LLM ---")
        print(messages)
        print("\n--- LLM invocation parameters ---")
        pprint(kwargs.get("invocation_params", {}))
        print("\n--- LLM options ---")
        pprint(kwargs.get("options", {}))

    def on_llm_end(self, response, **kwargs):
        print("\n--- Raw response from LLM ---")
        print(response)


# Define custom tool

@tool
def multiply(a: Union[int, float], b: int) -> Union[float, int]:
    """Multiply two numbers together."""
    return a * b


@tool
def divide(a: int, b: int) -> float:
    """Divide two integers together."""
    return a / b

#
# class Column(BaseModel):
#     name:str
#     type:str
#
# class Table(BaseModel):
#     name:str
#     columns: List[Column]
#
# class Catalog(BaseModel):
#     tables: List[Table]
#
# @tool
# def find_catalog() -> Catalog:
#     """Find accessible data catalog."""
#     return Catalog({})
#
#
# @tool
# def execute_sql(select_statement: str) -> dict:
#     """Multiply two numbers together."""
#     return {'records': []}
#
# @tool
# def get_recent_purchases(user_name: str) -> dict:
#     """Multiply two numbers together."""
#     return {'products': []}
#
# user_prompt = "give top 10 product recommendations based on past purchases for user: {username}"

tools = [multiply, divide]
model = ChatOpenAI(
    model=os.environ['OPENAI_MODEL'],
    reasoning_effort="none",
    callbacks=[LLMTraceHandler()],
)

# Create ReAct Agent executor
agent_executor = create_agent(
    model = model,
    tools = tools,
    system_prompt=(
        "DO NOT do the calculation using LLM for existing tools."
        " Rely on the output from tool calling."
    )
)

# Invoke Agent
events = agent_executor.invoke({"messages": [
    ("user", "What is 14.5 multiplied by 22?"),
    ("user", "Add 100 to the previous response"),
    ("user", "Divide the response by 10")
]})
print("AI response: ", events["messages"][-1].content)
