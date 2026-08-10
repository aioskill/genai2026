"""A LangGraph shopping assistant that looks up prices and applies discounts.

The graph has two nodes:

    START -> assistant - tool calls -> tools -> assistant
                         +-- no tool call -> END

The assistant node asks the model what to do. When the model requests a tool,
the tools node executes it and adds a ``ToolMessage`` to the shared state. The
assistant then sees that result and either calls the next tool or writes the
final answer.

This is deliberately written with ``StateGraph`` instead of a high-level agent
constructor so beginners can see the state, nodes, router, and loop directly.
Before running it, configure ``OPENAI_MODEL`` and the OpenAI credentials in
``.env``.
"""

import os
from difflib import get_close_matches
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import ToolException, tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langsmith import traceable

load_dotenv()
MAX_ITERATIONS = 10


# --- Tools ---------------------------------------------------------------

@tool
def get_product_price(product: str) -> dict:
    """Look up the price of a product in the catalog.

    A successful lookup returns the product and its price. An unknown product
    raises ``ToolException`` instead of returning a ``found`` flag. LangChain
    treats that exception as a tool failure, and the graph sends its message
    back to the model in a ``ToolMessage``.
    """
    print(f"    >> Executing get_product_price(product='{product}')")
    prices = {"laptop": 1299.99, "headphones": 149.95, "keyboard": 89.50}

    if product in prices:
        return {"product": product, "price": prices[product]}

    suggestions = get_close_matches(product, prices.keys(), n=3, cutoff=0.4)
    suggestion_text = (
        f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
    )
    raise ToolException(
        f"Product '{product}' not found in catalog.{suggestion_text}"
    )


@tool
def apply_discount(price: float, discount_tier: str) -> float:
    """Apply bronze, silver, or gold discount to a price."""
    print(
        f"    >> Executing apply_discount(price={price}, "
        f"discount_tier='{discount_tier}')"
    )
    discount_percentages = {"bronze": 5, "silver": 12, "gold": 23}
    discount = discount_percentages.get(discount_tier, 0)
    return round(price * (1 - discount / 100), 2)


TOOLS = [get_product_price, apply_discount]
TOOLS_BY_NAME = {item.name: item for item in TOOLS}

llm = ChatOpenAI(
    model=os.environ["OPENAI_MODEL"],
    reasoning_effort="none",
)
llm_with_tools = llm.bind_tools(TOOLS)


# --- Graph state and nodes -----------------------------------------------

class ShoppingState(TypedDict):
    """Messages are the graph's shared memory.

    ``add_messages`` tells LangGraph to append new messages rather than
    replacing the existing conversation after each node.
    """

    messages: Annotated[list[AnyMessage], add_messages]


SYSTEM_PROMPT = """You are a helpful shopping assistant.

Follow these rules exactly:
1. Never guess a product price. Call get_product_price first.
2. Call apply_discount only after receiving a price from get_product_price.
3. Never calculate a discount yourself; always call apply_discount.
4. If no discount tier is provided, ask the user which tier to use.
5. If the catalog tool reports that a product is unavailable, do not call
   apply_discount. Explain the problem and mention any suggested alternative.
"""


def assistant_node(state: ShoppingState) -> dict:
    """Ask the model for the next action or the final response."""
    response = llm_with_tools.invoke(state["messages"])
    if response.tool_calls:
        print(f"  [Assistant requested] {[call['name'] for call in response.tool_calls]}")
    else:
        print("  [Assistant produced final answer]")
    return {"messages": [response]}


def tools_node(state: ShoppingState) -> dict:
    """Execute every tool call from the latest assistant message.

    Tool errors are converted to ``ToolMessage`` objects so the model can
    recover conversationally. The original invalid-product behavior still
    originates from ``get_product_price`` raising ``ToolException``.
    """
    assistant_message = state["messages"][-1]
    tool_messages = []

    for tool_call in assistant_message.tool_calls:
        name = tool_call["name"]
        tool = TOOLS_BY_NAME.get(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' not found")

        print(f"  [Tool Selected] {name} with args: {tool_call['args']}")
        try:
            result = tool.invoke(tool_call["args"])
        except ToolException as exc:
            result = str(exc)
        except Exception as exc:
            result = f"Tool execution failed: {exc}"

        print(f"  [Tool Result] {result}")
        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"])
        )

    return {"messages": tool_messages}


def route_after_assistant(state: ShoppingState) -> str:
    """Route tool requests to ``tools`` and ordinary responses to ``END``."""
    latest_message = state["messages"][-1]
    return "tools" if latest_message.tool_calls else "end"


# --- Graph construction --------------------------------------------------

builder = StateGraph(ShoppingState)
builder.add_node("assistant", assistant_node)
builder.add_node("tools", tools_node)
builder.add_edge(START, "assistant")
builder.add_conditional_edges(
    "assistant",
    route_after_assistant,
    {"tools": "tools", "end": END},
)
builder.add_edge("tools", "assistant")
shopping_graph = builder.compile()


@traceable(name="LangGraph Shopping Agent")
def run_agent(question: str) -> str:
    """Run the graph and return the final assistant message."""
    initial_state = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=question),
        ]
    }

    print(f"Question: {question}")
    print("=" * 60)
    final_state = shopping_graph.invoke(
        initial_state,
        config={"recursion_limit": MAX_ITERATIONS * 2},
    )
    final_message = final_state["messages"][-1]
    print(f"\nFinal Answer: {final_message.content}")
    return final_message.content


if __name__ == "__main__":
    run_agent("What is the price of a laptop after applying a gold discount?")
