"""A small LangGraph program that generates, tests, and repairs Python code.

This example is intended as a first look at LangGraph. The important idea is
that a graph is a workflow whose nodes read and update a shared ``state``.
Here the workflow is:

    START -> generate -> execute - success -----------------> END
                              +-- failure and attempts < 3 -> generate
                              +-- failure and attempts >= 3 -> END

The ``generate`` node asks the language model for code. The ``execute`` node
runs that code with Python and stores either success or the error traceback in
the state. On the next trip through ``generate``, the traceback becomes part
of the prompt, allowing the model to try a repair.

Before running this file, configure ``OPENAI_MODEL`` in a ``.env`` file and
make sure the corresponding OpenAI credentials are available. This is a
teaching example, not a production sandbox: running model-generated code with
``subprocess`` can be unsafe, so real applications should use an isolated
container or another restricted execution service.
"""

import os
import subprocess

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

load_dotenv()

from typing import TypedDict, Optional

class CodeAgentState(TypedDict):
    """The data (the graph's memory) passed between nodes.

    A node does not need to return every field. It returns only the fields it
    changed, and LangGraph merges that update into the current state.
    """

    user_requirement: str         # The original task the user wants solved.
    generated_code: str           # The latest Python code returned by the LLM.
    error_message: Optional[str]  # None, or the last execution error.
    iterations: int               # Number of generation attempts so far.
    is_success: bool              # Whether the latest execution succeeded.

llm = ChatOpenAI(model=os.environ["OPENAI_MODEL"],
                 reasoning_effort="none",
                 )


def generate_code_node(state: CodeAgentState) -> dict:
    """Generate a first draft, or ask the LLM to repair the previous draft.

    ``state.get("error_message")`` is the branch that makes this an iterative
    workflow rather than a one-shot LLM call. The LLM response is text, so the
    markdown fences are removed before the code is sent to the executor.
    """

    if state.get("error_message"):
        # Fix Code Prompt
        prompt = f"""Fix the Python code below.
Task: {state['user_requirement']}
Faulty Code: {state['generated_code']}
Error Traceback: {state['error_message']}

Return ONLY valid, executable Python code inside standard markdown blocks."""
    else:
        # Initial Draft Prompt
        prompt = f"Write Python code to solve: {state['user_requirement']}. Return ONLY Python code."
    response = llm.invoke(prompt)
    # Extract clean code block string
    code = response.content.replace("```python", "").replace("```", "").strip()

    return {
        "generated_code": code,
        "iterations": state.get("iterations", 0) + 1
    }


def execute_code_node(state: CodeAgentState) -> dict:
    """Run the current draft and write the result back into graph state.

    ``returncode == 0`` means Python finished without an exception. Any stderr
    output is saved as ``error_message`` so the generator can see what went
    wrong on a retry. The timeout is another guard against an infinite loop
    inside generated code, although it is not a complete security boundary.
    """

    code = state["generated_code"]
    try:
        # Execute python script via subprocess
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return {"error_message": None, "is_success": True}
        else:
            return {"error_message": result.stderr, "is_success": False}
    except Exception as e:
        return {"error_message": str(e), "is_success": False}



def decide_next_step(state: CodeAgentState) -> str:
    """Choose the next edge after execution.

    This is a LangGraph router: its return value must match one of the keys in
    the mapping passed to ``add_conditional_edges`` below.
    """
    if state["is_success"]:
        return "end" # Code executed successfully!
    elif state["iterations"] >= 3:
        return "end" # Reached max attempts, stop trying
    else:
        return "generate" # Loop back to generator node

# Build the graph. ``StateGraph(CodeAgentState)`` tells LangGraph the shape of
# the shared state; the calls below define nodes and the edges between them.
builder = StateGraph(CodeAgentState)

builder.add_node("generate", generate_code_node)
builder.add_node("execute", execute_code_node)

builder.add_edge(START, "generate")
builder.add_edge("generate", "execute")

# After ``execute``, use the router to either finish or loop back to ``generate``.
builder.add_conditional_edges(
    "execute",
    decide_next_step,
    {
        "generate": "generate", # Retry loop
        "end": END              # Exit graph
    }
)

code_graph = builder.compile()

# ``compile`` validates the graph and returns a runnable application. It does
# not call the LLM yet; the model is called only when the graph reaches the
# ``generate`` node during ``stream`` below.

# The first state supplies values for every field. Subsequent node updates are
# merged into this dictionary by LangGraph.

user_request = "Create a function to parse a JSON string, convert keys to camelCase, and return a dictionary."

initial_input = {
    "user_requirement": user_request,
    "generated_code": "",
    "error_message": None,
    "iterations": 0,
    "is_success": False
}

print("User request: ", user_request)

print("=== STARTING GRAPH STREAM ===")

final_state = {}

# ``stream`` yields an event after each completed node. Each event is shaped
# like ``{"node_name": {"changed_field": value}}``. Printing the node name
# makes the graph's execution order visible to a learner.
for event in code_graph.stream(initial_input):
    for node_name, state_update in event.items():
        print(f"\n[Completed Node: {node_name}]")
        final_state.update(state_update) # Save state updates

# The final state contains the latest draft, whether it passed or the graph
# stopped after three attempts.
print("\n" + "="*40)
print("     FULL GENERATED PYTHON CODE")
print("="*40 + "\n")
print(final_state.get("generated_code"))

# Check total loop count
print(f"Total Loops / Attempts: {final_state['iterations']}")
