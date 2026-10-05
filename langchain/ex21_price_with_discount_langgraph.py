"""A LangGraph shopping assistant that looks up prices and applies discounts.

The graph has three stages:

    START -> find_valid_product -> find_valid_discount_tier -> final_price
                                      (optional)

The first two stages ask the model to call their matching tools. The final
stage looks up the product price and applies the matched tier when available.

This is deliberately written with ``StateGraph`` instead of a high-level agent
constructor so beginners can see the state, nodes, router, and loop directly.
Before running it, configure ``OPENAI_MODEL`` and the OpenAI credentials in
``.env``.
"""

import os
from difflib import get_close_matches
from typing import Annotated, List, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import ToolException, tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langsmith import traceable

load_dotenv()
MAX_ITERATIONS = 10


# --- Tools ---------------------------------------------------------------

PRICES = {"laptop": 1299.99, "headphones": 149.95, "keyboard": 89.50}
DISCOUNT_TIERS = ["bronze", "silver", "gold"]


@tool
def find_product_match(product: str) -> List[str]:
    """Find catalog product names similar to the supplied name."""
    return get_close_matches(
        product.lower(), PRICES.keys(), n=3, cutoff=0.4
    )


@tool
def find_discount_tier_match(discount_tier: str) -> List[str]:
    """Find discount tiers similar to the supplied tier."""
    return get_close_matches(
        discount_tier.lower(), DISCOUNT_TIERS, n=3, cutoff=0.4
    )


@tool
def get_product_price(product: str) -> dict:
    """Look up the price of a product in the catalog.

    A successful lookup returns the product and its price. An unknown product
    raises ``ToolException`` instead of returning a ``found`` flag. LangChain
    treats that exception as a tool failure, and the graph sends its message
    back to the model in a ``ToolMessage``.
    """
    print(f"    >> Executing get_product_price(product='{product}')")

    normalized_product = product.lower()
    if normalized_product in PRICES:
        return {
            "product": normalized_product,
            "price": PRICES[normalized_product],
        }

    raise ToolException(f"Product '{product}' not found in catalog.")


@tool
def apply_discount(price: float, discount_tier: str) -> float:
    """Apply bronze, silver, or gold discount to a price."""
    print(
        f"    >> Executing apply_discount(price={price}, "
        f"discount_tier='{discount_tier}')"
    )
    discount_percentages = {"bronze": 5, "silver": 12, "gold": 23}
    normalized_tier = discount_tier.lower()
    if normalized_tier not in discount_percentages:
        raise ToolException(f"Unknown discount tier '{discount_tier}'.")

    discount = discount_percentages[normalized_tier]
    return round(price * (1 - discount / 100), 2)


llm = ChatOpenAI(
    model=os.environ["OPENAI_MODEL"],
    reasoning_effort="none",
)
TOOLS = [
    find_product_match,
    find_discount_tier_match,
    get_product_price,
    apply_discount,
]
TOOLS_BY_NAME = {item.name: item for item in TOOLS}
llm_with_tools = llm.bind_tools(TOOLS, parallel_tool_calls=False)


# --- Graph state and nodes -----------------------------------------------

class ShoppingState(TypedDict):
    """Conversation messages and collected shopping calculation values."""

    messages: Annotated[list[AnyMessage], add_messages]
    product_name: str | None
    product_name_identified: bool
    list_price: float | None
    discount_tier: str | None
    discount_tier_identified: bool
    discounted_price: float | None


SYSTEM_PROMPT = """You are a helpful shopping assistant.

Follow these rules:
1. Use find_product_match when identifying a product name. Use a returned
   catalog name with get_product_price; never guess a price.
2. If the user names a discount tier, use find_discount_tier_match to identify
   it, then call apply_discount after receiving the product price.
3. Ask which tier to use only if the user did not provide one.
4. Never calculate a discount yourself.
5. If a match tool returns no useful result, ask the user to clarify.
6. If a product or discount tool reports an error, explain it and do not
   invent a result.
"""


def assistant_node(state: ShoppingState) -> dict:
    """Ask the model to select its next tool call or provide a final answer."""
    response = llm_with_tools.invoke(state["messages"])
    if response.tool_calls:
        selected_tools = [call["name"] for call in response.tool_calls]
        print(f"  [Assistant requested] {selected_tools}")
    else:
        print("  [Assistant produced final answer]")
    return {"messages": [response]}


def tools_node(state: ShoppingState) -> dict:
    """Execute the tools requested by the latest assistant message."""
    assistant_message = state["messages"][-1]
    tool_messages = []
    collected_values = {}

    for tool_call in assistant_message.tool_calls:
        name = tool_call["name"]
        selected_tool = TOOLS_BY_NAME.get(name)
        if selected_tool is None:
            raise ValueError(f"Tool '{name}' not found")

        print(f"  [Tool Selected] {name} with args: {tool_call['args']}")
        try:
            result = selected_tool.invoke(tool_call["args"])
        except ToolException as exc:
            result = str(exc)
        except Exception as exc:
            result = f"Tool execution failed: {exc}"

        if name == "get_product_price" and isinstance(result, dict):
            collected_values["product_name"] = result["product"]
            collected_values["product_name_identified"] = True
            collected_values["list_price"] = result["price"]
        elif name == "apply_discount" and isinstance(result, (int, float)):
            tier = tool_call["args"]["discount_tier"].lower()
            collected_values["discount_tier"] = tier
            collected_values["discount_tier_identified"] = True
            collected_values["discounted_price"] = result

        print(f"  [Tool Result] {result}")
        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"])
        )

    collected_values["messages"] = tool_messages
    return collected_values


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
    """Run the graph and return its final assistant message."""
    initial_state = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=question),
        ],
        "product_name": None,
        "product_name_identified": False,
        "list_price": None,
        "discount_tier": None,
        "discount_tier_identified": False,
        "discounted_price": None,
    }

    print(f"Question: {question}")
    print("=" * 60)
    final_state = shopping_graph.invoke(
        initial_state,
        config=RunnableConfig(recursion_limit=MAX_ITERATIONS * 2),
    )
    final_answer = final_state["messages"][-1].content
    print(f"\nFinal Answer: {final_answer}")
    print(
        "Collected values: "
        f"product={final_state['product_name']}, "
        f"list_price={final_state['list_price']}, "
        f"discount_tier={final_state['discount_tier']}, "
        f"discounted_price={final_state['discounted_price']}"
    )
    return final_answer


if __name__ == "__main__":
    run_agent("What is the price of a LAPTOP after applying a golf discount?")
