import os
from pprint import pprint

from langchain_core.tools import tool
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from dotenv import load_dotenv
from typing import Union

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
def multiply(a: Union[int, float], b: int) -> float:
    """Multiply two integers together."""
    return a * b


@tool
def divide(a: int, b: int) -> float:
    """Divide two integers together."""
    return a / b


tools = [multiply, divide]
model = ChatOpenAI(
    model=os.environ['OPENAI_MODEL'],
    reasoning_effort="none",
    callbacks=[LLMTraceHandler()],
)

# Create ReAct Agent executor
agent_executor = create_agent(
    model, tools,
    system_prompt=(
        "DO NOT do the calculation using LLM for existing tools."
        " Rely on the output from tool calling."
    )
)

# Invoke Agent
events = agent_executor.invoke({"messages": [
    ("user", "What is 14.5 multiplied by 22?"),
    ("user", "Add 100 to the previous response")
]})
print(events["messages"][-1].content)
