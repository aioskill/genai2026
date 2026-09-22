import argparse
import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
import json
import os
import tempfile
from typing import Any, AsyncIterator

from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

from bootstrap import run_bootstrap

# Server SSE Endpoints
SERVERS = {
    "SQL_Tickets": "http://localhost:8001/sse",
    "Chroma_Resolutions": "http://localhost:8002/sse",
    "Patch_Executor": "http://localhost:8003/sse"
}

HITL_PROTECTED_TOOLS = {"apply_code_patch"}
DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_MAX_ITERATIONS = 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the multi-server MCP orchestrator."
    )
    parser.add_argument(
        "--disable-hitl",
        action="store_true",
        help="Bypass the human-in-the-loop approval gate for protected tools.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Seconds to wait between ticket-processing iterations.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help="Maximum number of ticket-processing iterations.",
    )
    return parser.parse_args()


def _coerce_json(payload):
    if not isinstance(payload, str):
        return payload

    text = payload.strip()
    if not text:
        return text

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        values = []
        idx = 0
        length = len(text)
        while idx < length:
            while idx < length and text[idx].isspace():
                idx += 1
            if idx >= length:
                break
            value, end = decoder.raw_decode(text, idx)
            values.append(value)
            idx = end
        if values:
            return values if len(values) > 1 else values[0]
        return payload


class MCPOrchestrator:
    """Coordinate the ticket workflow across the MCP servers."""

    def __init__(
        self,
        disable_hitl: bool = False,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ):
        self.disable_hitl = disable_hitl
        self.interval_seconds = interval_seconds
        self.max_iterations = max_iterations
        self.sessions: dict[str, ClientSession] = {}
        self._validate_configuration()

    async def run(self) -> None:
        self._print_startup()
        async with self._connected_sessions():
            await self._initialize_sessions()
            await self._run_bootstrap()
            await self._run_polling_loop()

    def _validate_configuration(self) -> None:
        if self.interval_seconds < 0:
            raise ValueError("interval_seconds must be zero or greater")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be greater than zero")

    async def _run_polling_loop(
        self,
    ) -> None:
        for iteration in range(self.max_iterations):
            print(
                f"\n=== Ticket polling iteration "
                f"{iteration + 1}/{self.max_iterations} ==="
            )
            await self._process_open_tickets()
            if iteration + 1 < self.max_iterations:
                await asyncio.sleep(self.interval_seconds)

    def _print_startup(self) -> None:
        base_tmp_dir = os.path.join(tempfile.gettempdir(), "mcp_ex1")
        print("=== Multi-Server MCP Orchestrator Starting ===")
        print(f"Root Workspace Directory: {base_tmp_dir}\n")

    @asynccontextmanager
    async def _connected_sessions(
        self,
    ) -> AsyncIterator[None]:
        sessions = {}
        async with AsyncExitStack() as stack:
            for server_name, endpoint in SERVERS.items():
                read_stream, write_stream = await stack.enter_async_context(
                    sse_client(endpoint)
                )
                sessions[server_name] = await stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
            self.sessions = sessions
            try:
                yield
            finally:
                self.sessions = {}

    async def _initialize_sessions(self) -> None:
        await asyncio.gather(
            *(session.initialize() for session in self.sessions.values())
        )
        print("Connected to all 3 MCP Servers successfully!\n")

    async def _run_bootstrap(self) -> None:
        print("Running bootstrap to seed required records...")
        await run_bootstrap()
        print("Bootstrap completed.\n")

    async def _process_open_tickets(self) -> None:
        open_tickets = await self._list_open_tickets()
        print(f"Open tickets: {open_tickets}")

        for index, summary_ticket in enumerate(open_tickets, start=1):
            await self._process_ticket(
                summary_ticket,
                index,
                len(open_tickets),
            )

    async def _list_open_tickets(self) -> list:
        response = await self._execute_tool(
            "SQL_Tickets",
            "list_open_tickets",
            {},
        )
        open_tickets = _coerce_json(response)
        if isinstance(open_tickets, dict):
            return [open_tickets]
        return open_tickets

    async def _process_ticket(
        self,
        summary_ticket: dict[str, Any],
        index: int,
        total: int,
    ) -> None:
        ticket_id = summary_ticket["ticket_id"]
        print(f"\n=== Processing Ticket {index}/{total}: {ticket_id} ===")
        ticket = await self._fetch_ticket(ticket_id)
        search_results = await self._search_resolutions(ticket)

        if search_results:
            await self._remediate_ticket(ticket_id, ticket)
        else:
            await self._escalate_ticket(ticket_id)

        await self._print_incident_rca(ticket_id)

    async def _fetch_ticket(
        self,
        ticket_id: str,
    ) -> dict:
        print(
            f"\n\n--- Step 2: Fetching details for {ticket_id} "
            "from SQL Server ---"
        )
        response = await self._execute_tool(
            "SQL_Tickets",
            "get_ticket_details",
            {"ticket_id": ticket_id},
        )
        ticket = _coerce_json(response)
        print(f"Live ticket context: {ticket}")
        return ticket

    async def _search_resolutions(
        self,
        ticket: dict[str, Any],
    ) -> Any:
        print("\n\n--- Step 3: Querying ChromaDB knowledge base ---")
        response = await self._execute_tool(
            "Chroma_Resolutions",
            "search_resolutions",
            {"description": ticket["title"]},
        )
        search_results = _coerce_json(response)
        print(f"Semantic matches: {search_results}")
        await self._print_latest_resolution()
        return search_results

    async def _print_latest_resolution(self) -> None:
        resource = await self.sessions["Chroma_Resolutions"].read_resource(
            "chroma://resolutions/latest"
        )
        resource_text = "\n".join(
            getattr(content, "text", str(content))
            for content in resource.contents
        )
        print("Latest Chroma resource snapshot:")
        print(resource_text)

    async def _remediate_ticket(
        self,
        ticket_id: str,
        ticket: dict[str, Any],
    ) -> None:
        patch_args = {
            "filename": ticket["affected_file"],
            "patch_content": '{\n  "connection_timeout_ms": 5000\n}',
        }
        print("\n\n--- Step 4: LLM proposes a configuration patch ---")
        patch_result = await self._execute_tool(
            "Patch_Executor",
            "apply_code_patch",
            patch_args,
        )
        await self._execute_tool(
            "SQL_Tickets",
            "save_patch_details",
            {
                "ticket_id": ticket_id,
                "filename": patch_args["filename"],
                "patch_content": patch_args["patch_content"],
                "patch_result": patch_result,
            },
        )

    async def _escalate_ticket(
        self,
        ticket_id: str,
    ) -> None:
        print(
            "No vector resolution found; escalating ticket to "
            "REQUIRE_HUMAN_FIX."
        )
        await self._execute_tool(
            "SQL_Tickets",
            "update_ticket_status",
            {"ticket_id": ticket_id, "status": "REQUIRE_HUMAN_FIX"},
        )

    async def _print_incident_rca(
        self,
        ticket_id: str,
    ) -> None:
        prompt_result = await self.sessions["SQL_Tickets"].get_prompt(
            "incident_rca",
            {"ticket_id": ticket_id},
        )
        prompt_text = "\n\n".join(
            message.content.text for message in prompt_result.messages
        )
        print(
            "\n\n--- Step 5: SQL Server returns the closing incident RCA "
            "prompt ---"
        )
        print(prompt_text)

    async def _execute_tool(
        self,
        server_name: str,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> str:
        print(f"\nAgent calling [{tool_name}] on Server <{server_name}>")
        print(f"   Payload: {tool_args}")

        if not await self._authorize_tool(server_name, tool_name, tool_args):
            return "Action rejected by Human."

        result = await self.sessions[server_name].call_tool(
            tool_name,
            tool_args,
        )
        output = self._tool_output(result)
        print(f"[{server_name}] Response: {output}")
        return output

    async def _authorize_tool(
        self,
        server_name: str,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> bool:
        if self.disable_hitl or tool_name not in HITL_PROTECTED_TOOLS:
            return True

        print("\n" + "--" * 100)
        print("HUMAN-IN-THE-LOOP SECURITY GATE INITIATED")
        print(f"Action: Modify production file on {server_name}")
        print(f"Target File: {tool_args.get('filename')}")
        print(f"Proposed Content:\n{tool_args.get('patch_content')}")
        print("---" * 15)

        approval = input(
            "Authorize this system patch? (y/N): "
        ).strip().lower()
        if approval == "y":
            return True

        print("Patch operation aborted by administrator.")
        return False

    @staticmethod
    def _tool_output(result: Any) -> str:
        if not result.content:
            return ""
        return "\n".join(
            getattr(content, "text", str(content))
            for content in result.content
        )


async def run_orchestrator(
    disable_hitl: bool = False,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> None:
    """Run the ticket workflow using the MCP orchestrator."""
    orchestrator = MCPOrchestrator(
        disable_hitl=disable_hitl,
        interval_seconds=interval_seconds,
        max_iterations=max_iterations,
    )
    await orchestrator.run()

if __name__ == "__main__":
    args = _parse_args()
    disable_hitl = args.disable_hitl or (
        os.getenv("MCP_DISABLE_HITL", "").lower()
        in {"1", "true", "yes", "on"}
    )
    asyncio.run(
        run_orchestrator(
            disable_hitl=disable_hitl,
            interval_seconds=args.interval_seconds,
            max_iterations=args.max_iterations,
        )
    )
