import os
from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, ToolException
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

# ==========================================
# CONFIG SWITCHER
# Select which scenario to run:
#
# EXPECTATIONS FOR INPUTS:
# - "hitl"  : Tests CASE A only.
#             Asks for approval on a valid SELECT query.
#             • Type 'y': Executes the query and returns 24 records.
#             • Type 'n': Cancels execution and notifies the model.
#
# - "error" : Tests CASE B only.
#             Asks for approval on a prohibited DROP TABLE query.
#             • Type 'y': Approves execution, which triggers a ToolException
#                         (DROP/DELETE blocked) and feeds the error back to
#                         the LLM for self-correction.
#             • Type 'n': Cancels execution before the tool even runs.
#
# - "both"  : Runs CASE A sequentially, followed by CASE B.

RUN_CASE = "both"  # Options: "hitl", "error", "both"


# ==========================================
# DEFINE DATABASE TOOL WITH ERROR HANDLING
# ==========================================

@tool
def query_database(query: str) -> str:
    """Execute an SQL query against the database."""
    # Safety validation: block destructive queries
    if "DROP" in query.upper() or "DELETE" in query.upper():
        raise ToolException("Destructive SQL operations (DROP/DELETE) are strictly prohibited.")

    return f"Execution successful for query: '{query}'. Results: [24 records returned]."


tools = [query_database]

model = ChatOpenAI(
    model=os.environ["OPENAI_MODEL"],
    reasoning_effort="none",
)

system_prompt = (
    "You are a database assistant with access to the query_database tool. "
    "When the user requests an SQL operation, execute the tool directly. "
    "Execution safety and human approval are handled externally."
)

checkpointer = MemorySaver()

# Create agent using langchain.agents standard constructor
agent = create_agent(
    model,
    tools,
    system_prompt=system_prompt,
    checkpointer=checkpointer,
    interrupt_before=["tools"],  # Pauses before tool execution node
)


# ==========================================
# HELPER: INTERACTIVE APPROVAL PROMPT
# ==========================================

def handle_human_approval(agent, config):
    """Prompts the user via stdin to approve or deny the pending tool call."""
    state = agent.get_state(config)

    # Check for pending tool calls
    if not state.values.get("messages") or not state.values["messages"][-1].tool_calls:
        print("\nNo pending tool call to approve.")
        return

    pending_tool = state.values["messages"][-1].tool_calls[0]

    print("\n" + "=" * 50)
    print("HUMAN APPROVAL REQUIRED")
    print(f" Tool Name : {pending_tool['name']}")
    print(f" Arguments : {pending_tool['args']}")
    print("=" * 50)

    # Ask for user input via stdin
    user_choice = input("\nDo you approve executing this tool? (y/n): ").strip().lower()

    if user_choice in ["y", "yes"]:
        print("\nAction Approved. Resuming execution...\n")
        # Resume normal tool execution
        for event in agent.stream(None, config, stream_mode="values"):
            event["messages"][-1].pretty_print()

    else:
        print("\nAction Denied by User. Notifying agent...\n")
        # Send a rejection message back to the LLM
        denial_message = ToolMessage(
            tool_call_id=pending_tool["id"],
            content="User denied execution permission for this query."
        )
        agent.update_state(config, {"messages": [denial_message]}, as_node="tools")
        for event in agent.stream(None, config, stream_mode="values"):
            event["messages"][-1].pretty_print()


# ------------------------------------------
# CASE A: Standard Read Query (HITL Flow)
# ------------------------------------------
if RUN_CASE in ["hitl", "both"]:
    print("=" * 60)
    print("RUNNING CASE A: Valid Query (Human Approval Flow)")
    print("=" * 60)

    config_hitl = {"configurable": {"thread_id": "session_valid_query"}}
    initial_input = {"messages": [("user", "Fetch all active users with status='active'")]}

    print("\n--- Running agent until tool interrupt ---")
    for event in agent.stream(initial_input, config_hitl, stream_mode="values"):
        event["messages"][-1].pretty_print()

    # Prompt user via stdin (Approval -> Success)
    handle_human_approval(agent, config_hitl)

# ------------------------------------------
# CASE B: Destructive Query (Error Recovery)
# ------------------------------------------
if RUN_CASE in ["error", "both"]:
    print("\n" + "=" * 60)
    print("RUNNING CASE B: Destructive Query (Tool Exception Flow)")
    print("=" * 60)

    config_err = {"configurable": {"thread_id": "session_destructive_query"}}
    bad_request = {"messages": [("user", "Clear the inactive users by running DROP TABLE inactive_users;")]}

    print("\n--- Running agent until tool interrupt ---")
    for event in agent.stream(bad_request, config_err, stream_mode="values"):
        event["messages"][-1].pretty_print()

    # Prompt user via stdin (Type 'y' to see tool throw ToolException and agent recover)
    handle_human_approval(agent, config_err)