import os

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
# from langgraph.prebuilt import create_react_agent
from langchain.agents import create_agent
from dotenv import load_dotenv

load_dotenv()

# Define custom tool
@tool
def multiply(a: int, b: int) -> int:
    """Multiply two integers together."""
    return a * b

tools = [multiply]
model = ChatOpenAI(
    model=os.environ['OPENAI_MODEL'],
    reasoning_effort="none",
)

# Create ReAct Agent executor
agent_executor = create_agent(model, tools)

# Invoke Agent
events = agent_executor.invoke({"messages": [("user", "What is 14 multiplied by 22?")]})
print(events["messages"][-1].content)