"""LangGraph orchestration for the multi-server ticket workflow."""

import argparse
import asyncio
import os
import tempfile
import uuid
from typing import TypedDict

from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

from bootstrap import run_bootstrap
from client import MCPOrchestrator, SERVERS


class GraphState(TypedDict, total=False):
    ticket_queue: list[dict]
    current_ticket: dict | None
    processed_tickets: list[str]
    iteration: int
    max_iterations: int


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the LangGraph multi-server MCP orchestrator."
    )
    parser.add_argument(
        "--disable-hitl",
        action="store_true",
        help="Bypass the human-in-the-loop approval gate for patches.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=60.0,
        help="Seconds to wait between ticket polling iterations.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=1,
        help="Maximum number of ticket polling iterations.",
    )
    return parser.parse_args()


async def _build_graph(
    orchestrator: MCPOrchestrator,
    max_iterations: int,
):
    async def load_open_tickets(state: GraphState) -> GraphState:
        tickets = await orchestrator._list_open_tickets()
        print(f"Open tickets: {tickets}")
        return {"ticket_queue": tickets}

    async def select_ticket(state: GraphState) -> GraphState:
        queue = list(state.get("ticket_queue", []))
        if not queue:
            return {"current_ticket": None}
        ticket = queue.pop(0)
        return {"current_ticket": ticket, "ticket_queue": queue}

    async def process_ticket(state: GraphState) -> GraphState:
        summary = state["current_ticket"]
        processed = list(state.get("processed_tickets", []))
        ticket_id = summary["ticket_id"]
        await orchestrator._process_ticket(
            summary,
            len(processed) + 1,
            len(processed) + len(state.get("ticket_queue", [])) + 1,
        )
        processed.append(ticket_id)
        return {"processed_tickets": processed}

    def route_after_selection(state: GraphState) -> str:
        if state.get("current_ticket"):
            return "process"
        if state.get("iteration", 1) < max_iterations:
            return "next_iteration"
        return "done"

    def route_after_ticket(state: GraphState) -> str:
        if state.get("ticket_queue"):
            return "next_ticket"
        next_iteration = state.get("iteration", 1) + 1
        if next_iteration <= max_iterations:
            return "next_iteration"
        return "done"

    async def start_next_iteration(state: GraphState) -> GraphState:
        interval = orchestrator.interval_seconds
        if interval:
            await asyncio.sleep(interval)
        iteration = state.get("iteration", 1) + 1
        print(
            f"\n=== Ticket polling iteration "
            f"{iteration}/{max_iterations} ==="
        )
        tickets = await orchestrator._list_open_tickets()
        print(f"Open tickets: {tickets}")
        return {"ticket_queue": tickets, "iteration": iteration}

    builder = StateGraph(GraphState)
    builder.add_node("load_open_tickets", load_open_tickets)
    builder.add_node("select_ticket", select_ticket)
    builder.add_node("process_ticket", process_ticket)
    builder.add_node("start_next_iteration", start_next_iteration)
    builder.add_edge(START, "load_open_tickets")
    builder.add_edge("load_open_tickets", "select_ticket")
    builder.add_conditional_edges(
        "select_ticket",
        route_after_selection,
        {
            "process": "process_ticket",
            "next_iteration": "start_next_iteration",
            "done": END,
        },
    )
    builder.add_conditional_edges(
        "process_ticket",
        route_after_ticket,
        {
            "next_ticket": "select_ticket",
            "next_iteration": "start_next_iteration",
            "done": END,
        },
    )
    builder.add_edge("start_next_iteration", "select_ticket")
    return builder.compile(checkpointer=InMemorySaver())


async def _run_graph(graph, max_iterations: int) -> dict:
    config = {"configurable": {"thread_id": f"mcp-lg-v2-{uuid.uuid4().hex}"}}
    state = {"iteration": 1, "max_iterations": max_iterations}
    print(f"\n=== Ticket polling iteration 1/{max_iterations} ===")
    async for event in graph.astream(
        state,
        config=config,
        stream_mode="updates",
        version="v2",
    ):
        updates = event.get("data", {})
        for node_name, update in updates.items():
            if isinstance(update, dict):
                state.update(update)
            print(f"[{node_name}] {update}")
    return state


async def main() -> None:
    load_dotenv()
    args = _parse_args()
    disable_hitl = args.disable_hitl or os.getenv(
        "MCP_DISABLE_HITL", ""
    ).lower() in {"1", "true", "yes", "on"}
    if args.interval_seconds < 0 or args.max_iterations < 1:
        raise ValueError("Polling interval and iteration count are invalid")

    workspace = os.path.join(tempfile.gettempdir(), "mcp_ex1")
    print("=== LangGraph v2 MCP Orchestrator Starting ===")
    print(f"Root Workspace Directory: {workspace}\n")
    orchestrator = MCPOrchestrator(
        disable_hitl=disable_hitl,
        interval_seconds=args.interval_seconds,
        max_iterations=args.max_iterations,
    )
    async with (
        sse_client(SERVERS["SQL_Tickets"]) as (sql_read, sql_write),
        sse_client(SERVERS["Chroma_Resolutions"]) as (
            chroma_read,
            chroma_write,
        ),
        sse_client(SERVERS["Patch_Executor"]) as (patch_read, patch_write),
    ):
        async with (
            ClientSession(sql_read, sql_write) as sql_session,
            ClientSession(chroma_read, chroma_write) as chroma_session,
            ClientSession(patch_read, patch_write) as patch_session,
        ):
            orchestrator.sessions = {
                "SQL_Tickets": sql_session,
                "Chroma_Resolutions": chroma_session,
                "Patch_Executor": patch_session,
            }
            initialization = [
                session.initialize()
                for session in orchestrator.sessions.values()
            ]
            await asyncio.gather(*initialization)
            print("Connected to all 3 MCP Servers successfully!\n")
            print("Running bootstrap to seed required records...")
            await run_bootstrap()
            print("Bootstrap completed.\n")
            graph = await _build_graph(orchestrator, args.max_iterations)
            await _run_graph(graph, args.max_iterations)


if __name__ == "__main__":
    asyncio.run(main())
