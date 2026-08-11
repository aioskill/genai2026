import argparse
import asyncio
import json
import os
import tempfile
import uuid
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from mcp.client.session import ClientSession
from bootstrap import run_bootstrap
from mcp.client.sse import sse_client

SERVERS = {
    "SQL_Tickets": "http://localhost:8001/sse",
    "Chroma_Resolutions": "http://localhost:8002/sse",
    "Patch_Executor": "http://localhost:8003/sse",
}

HITL_PROTECTED_TOOLS = {"apply_code_patch"}


class GraphState(TypedDict, total=False):
    ticket_queue: list[dict]
    current_ticket: dict
    current_ticket_details: dict
    search_results: list[dict]
    latest_resource_text: str
    patch_args: dict
    patch_result: str
    patch_save_result: dict
    rca_text: str
    rca_reports: list[dict]
    approved: bool


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LangGraph v2 MCP orchestrator.")
    parser.add_argument(
        "--disable-hitl",
        action="store_true",
        help="Bypass the human-in-the-loop approval gate for protected tools.",
    )
    return parser.parse_args()


def _coerce_json(payload):
    if isinstance(payload, str):
        return json.loads(payload)
    return payload


async def run_tool(session: ClientSession, tool_name: str, tool_args: dict) -> str:
    result = await session.call_tool(tool_name, tool_args)
    return result.content[0].text if result.content else ""


def _print_node_update(node_name: str, node_update) -> None:
    print(f"[{node_name}] progress:")
    if isinstance(node_update, (dict, list)):
        print(json.dumps(node_update, indent=2, sort_keys=True, default=str))
    else:
        print(node_update)


async def build_graph(
    sql_session: ClientSession,
    chroma_session: ClientSession,
    patch_session: ClientSession,
    disable_hitl: bool,
):
    async def load_open_tickets(state: GraphState) -> GraphState:
        response = await run_tool(sql_session, "list_open_tickets", {})
        tickets = _coerce_json(response)
        if isinstance(tickets, dict):
            tickets = [tickets]
        return {"ticket_queue": tickets, "rca_reports": []}

    async def select_ticket(state: GraphState) -> GraphState:
        queue = list(state.get("ticket_queue", []))
        if not queue:
            return {"current_ticket": None}
        current_ticket = queue.pop(0)
        return {"current_ticket": current_ticket, "ticket_queue": queue}

    async def fetch_ticket_details(state: GraphState) -> GraphState:
        ticket_id = state["current_ticket"]["ticket_id"]
        response = await run_tool(sql_session, "get_ticket_details", {"ticket_id": ticket_id})
        return {"current_ticket_details": _coerce_json(response)}

    async def search_knowledge(state: GraphState) -> GraphState:
        ticket = state["current_ticket_details"]
        search_response = await run_tool(
            chroma_session,
            "search_resolutions",
            {"description": ticket["title"]},
        )
        search_results = _coerce_json(search_response)
        resource = await chroma_session.read_resource("chroma://resolutions/latest")
        latest_resource_text = "\n".join(
            getattr(content, "text", str(content)) for content in resource.contents
        )
        return {
            "search_results": search_results,
            "latest_resource_text": latest_resource_text,
        }

    async def escalate_no_match(state: GraphState) -> GraphState:
        ticket_id = state["current_ticket_details"]["ticket_id"]
        await run_tool(
            sql_session,
            "update_ticket_status",
            {"ticket_id": ticket_id, "status": "REQUIRE_HUMAN_FIX"},
        )
        return {"patch_result": "No vector resolution found; escalated to REQUIRE_HUMAN_FIX."}

    async def prepare_patch(state: GraphState) -> GraphState:
        ticket = state["current_ticket_details"]
        return {
            "patch_args": {
                "filename": ticket["affected_file"],
                "patch_content": '{\n  "connection_timeout_ms": 5000\n}',
            }
        }

    async def review_patch(state: GraphState) -> GraphState:
        if disable_hitl:
            return {"approved": True}

        ticket = state["current_ticket_details"]
        patch_args = state["patch_args"]
        decision = interrupt(
            {
                "ticket_id": ticket["ticket_id"],
                "filename": patch_args["filename"],
                "patch_content": patch_args["patch_content"],
                "prompt": "Authorize this system patch? (y/N)",
            }
        )
        return {"approved": bool(decision)}

    async def apply_patch(state: GraphState) -> GraphState:
        patch_args = state["patch_args"]
        result = await run_tool(patch_session, "apply_code_patch", patch_args)
        return {"patch_result": result}

    async def save_patch(state: GraphState) -> GraphState:
        ticket = state["current_ticket_details"]
        patch_args = state["patch_args"]
        patch_result = state["patch_result"]
        save_result = await run_tool(
            sql_session,
            "save_patch_details",
            {
                "ticket_id": ticket["ticket_id"],
                "filename": patch_args["filename"],
                "patch_content": patch_args["patch_content"],
                "patch_result": patch_result,
            },
        )
        return {"patch_save_result": _coerce_json(save_result)}

    async def generate_rca(state: GraphState) -> GraphState:
        ticket = state["current_ticket_details"]
        prompt = await sql_session.get_prompt("incident_rca", {"ticket_id": ticket["ticket_id"]})
        rca_text = "\n\n".join(message.content.text for message in prompt.messages)
        reports = list(state.get("rca_reports", []))
        reports.append({"ticket_id": ticket["ticket_id"], "rca_text": rca_text})
        return {"rca_text": rca_text, "rca_reports": reports}

    def route_after_selection(state: GraphState) -> str:
        return "done" if state.get("current_ticket") is None else "details"

    def route_after_search(state: GraphState) -> str:
        return "escalate" if not state.get("search_results") else "patch"

    def route_after_review(state: GraphState) -> str:
        return "apply" if state.get("approved") else "escalate"

    def route_after_rca(state: GraphState) -> str:
        return "continue" if state.get("ticket_queue") else "done"

    builder = StateGraph(GraphState)
    builder.add_node("load_open_tickets", load_open_tickets)
    builder.add_node("select_ticket", select_ticket)
    builder.add_node("fetch_ticket_details", fetch_ticket_details)
    builder.add_node("search_knowledge", search_knowledge)
    builder.add_node("escalate_no_match", escalate_no_match)
    builder.add_node("prepare_patch", prepare_patch)
    builder.add_node("review_patch", review_patch)
    builder.add_node("apply_patch", apply_patch)
    builder.add_node("save_patch", save_patch)
    builder.add_node("generate_rca", generate_rca)

    builder.add_edge(START, "load_open_tickets")
    builder.add_edge("load_open_tickets", "select_ticket")
    builder.add_conditional_edges(
        "select_ticket",
        route_after_selection,
        {"details": "fetch_ticket_details", "done": END},
    )
    builder.add_edge("fetch_ticket_details", "search_knowledge")
    builder.add_conditional_edges(
        "search_knowledge",
        route_after_search,
        {"patch": "prepare_patch", "escalate": "escalate_no_match"},
    )
    builder.add_edge("escalate_no_match", "generate_rca")
    builder.add_edge("prepare_patch", "review_patch")
    builder.add_conditional_edges(
        "review_patch",
        route_after_review,
        {"apply": "apply_patch", "escalate": "escalate_no_match"},
    )
    builder.add_edge("apply_patch", "save_patch")
    builder.add_edge("save_patch", "generate_rca")
    builder.add_conditional_edges(
        "generate_rca",
        route_after_rca,
        {"continue": "select_ticket", "done": END},
    )

    return builder.compile(checkpointer=InMemorySaver())


async def run_graph(graph, disable_hitl: bool):
    config = {"configurable": {"thread_id": f"mcp-lg-v2-{uuid.uuid4().hex}"}}
    input_payload: dict | Command = {}
    final_state: dict = {}

    while True:
        interrupted = False
        async for event in graph.astream(input_payload, config=config, stream_mode="updates", version="v2"):
            updates = event.get("data", {}) if isinstance(event, dict) else {}
            interrupt_payload = updates.get("__interrupt__") if isinstance(updates, dict) else None
            if interrupt_payload:
                print("HITL review requested:")
                print(interrupt_payload[0].value)

                if disable_hitl:
                    resume_value = True
                    print("HITL disabled; auto-approving patch.")
                else:
                    approval = input("Authorize this system patch? (y/N): ").strip().lower()
                    resume_value = approval == "y"

                input_payload = Command(resume=resume_value)
                interrupted = True
                break

            for node_name, node_update in updates.items():
                if node_name == "__interrupt__":
                    continue
                if isinstance(node_update, dict):
                    final_state.update(node_update)
                else:
                    final_state[node_name] = node_update
                _print_node_update(node_name, node_update)

        if interrupted:
            continue
        return final_state


async def main():
    args = _parse_args()
    disable_hitl = args.disable_hitl or os.getenv("MCP_DISABLE_HITL", "").lower() in {"1", "true", "yes", "on"}
    base_tmp_dir = os.path.join(tempfile.gettempdir(), "mcp_ex1")
    print(f"=== LangGraph v2 MCP Orchestrator Starting ===")
    print(f"Root Workspace Directory: {base_tmp_dir}\n")

    async with sse_client(SERVERS["SQL_Tickets"]) as (r1, w1), \
            sse_client(SERVERS["Chroma_Resolutions"]) as (r2, w2), \
            sse_client(SERVERS["Patch_Executor"]) as (r3, w3):
        async with ClientSession(r1, w1) as sql_session, \
                ClientSession(r2, w2) as chroma_session, \
                ClientSession(r3, w3) as patch_session:
            await asyncio.gather(
                sql_session.initialize(),
                chroma_session.initialize(),
                patch_session.initialize(),
            )
            print("Running bootstrap to seed required records...")
            await run_bootstrap()
            print("Bootstrap completed.\n")
            graph = await build_graph(sql_session, chroma_session, patch_session, disable_hitl)
            final_state = await run_graph(graph, disable_hitl)
            print("\nFinal RCA outputs:")
            for report in final_state.get("rca_reports", []):
                print(f"--- {report['ticket_id']} ---")
                print(report["rca_text"])


if __name__ == "__main__":
    asyncio.run(main())
