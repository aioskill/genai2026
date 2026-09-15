import argparse
import asyncio
import json
import os
import tempfile
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the multi-server MCP orchestrator.")
    parser.add_argument(
        "--disable-hitl",
        action="store_true",
        help="Bypass the human-in-the-loop approval gate for protected tools.",
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


async def run_orchestrator(disable_hitl: bool = False):
    base_tmp_dir = os.path.join(tempfile.gettempdir(), "mcp_ex1")
    print(f"=== Multi-Server MCP Orchestrator Starting ===")
    print(f"Root Workspace Directory: {base_tmp_dir}\n")

    # Establish SSE connections to all 3 servers
    async with sse_client(SERVERS["SQL_Tickets"]) as (r1, w1), \
            sse_client(SERVERS["Chroma_Resolutions"]) as (r2, w2), \
            sse_client(SERVERS["Patch_Executor"]) as (r3, w3):

        async with ClientSession(r1, w1) as sql_session, \
                ClientSession(r2, w2) as chroma_session, \
                ClientSession(r3, w3) as patch_session:

            await asyncio.gather(
                sql_session.initialize(),
                chroma_session.initialize(),
                patch_session.initialize()
            )
            print("Connected to all 3 MCP Servers successfully!\n")
            print("Running bootstrap to seed required records...")
            await run_bootstrap()
            print("Bootstrap completed.\n")

            async def execute_tool(session: ClientSession, server_name: str, tool_name: str, tool_args: dict):
                print(f"\nAgent calling [{tool_name}] on Server <{server_name}>")
                print(f"   Payload: {tool_args}")

                # HITL Interceptor Gate
                if tool_name in HITL_PROTECTED_TOOLS and not disable_hitl:
                    print("\n" + "--" * 100)
                    print(f"HUMAN-IN-THE-LOOP SECURITY GATE INITIATED")
                    print(f"Action: Modify production file on {server_name}")
                    print(f"Target File: {tool_args.get('filename')}")
                    print(f"Proposed Content:\n{tool_args.get('patch_content')}")
                    print("---" * 15)

                    approval = input("Authorize this system patch? (y/N): ").strip().lower()
                    if approval != 'y':
                        print("Patch operation aborted by administrator.")
                        return "Action rejected by Human."

                result = await session.call_tool(tool_name, tool_args)
                if result.content:
                    output = "\n".join(getattr(content, "text", str(content)) for content in result.content)
                else:
                    output = ""
                print(f"[{server_name}] Response: {output}")
                return output

            # --- Client Flow ---

            # Step 1: Discover the current open tickets.
            open_tickets_json = await execute_tool(
                sql_session,
                "SQL_Tickets",
                "list_open_tickets",
                {}
            )
            open_tickets = _coerce_json(open_tickets_json)
            if isinstance(open_tickets, dict):
                open_tickets = [open_tickets]

            print(f"Open tickets: {open_tickets}")

            for index, summary_ticket in enumerate(open_tickets, start=1):
                ticket_id = summary_ticket["ticket_id"]
                print(f"\n=== Processing Ticket {index}/{len(open_tickets)}: {ticket_id} ===")

                # Step 2: Inspect the selected ticket in SQL Server.
                print(f"\n\n--- Step 2: Fetching details for {ticket_id} from SQL Server ---")
                ticket_json = await execute_tool(
                    sql_session,
                    "SQL_Tickets",
                    "get_ticket_details",
                    {"ticket_id": ticket_id}
                )
                ticket = _coerce_json(ticket_json)
                print(f"Live ticket context: {ticket}")

                # Step 3: Search historical fixes and read the latest resolution resource.
                print("\n\n--- Step 3: Querying ChromaDB knowledge base ---")
                search_result_json = await execute_tool(
                    chroma_session,
                    "Chroma_Resolutions",
                    "search_resolutions",
                    {"description": ticket["title"]}
                )
                search_results = _coerce_json(search_result_json)
                print(f"Semantic matches: {search_results}")

                latest_resource = await chroma_session.read_resource("chroma://resolutions/latest")
                latest_resource_text = "\n".join(
                    getattr(content, "text", str(content)) for content in latest_resource.contents
                )
                print("Latest Chroma resource snapshot:")
                print(latest_resource_text)

                if not search_results:
                    print("No vector resolution found; escalating ticket to REQUIRE_HUMAN_FIX.")
                    await execute_tool(
                        sql_session,
                        "SQL_Tickets",
                        "update_ticket_status",
                        {
                            "ticket_id": ticket_id,
                            "status": "REQUIRE_HUMAN_FIX",
                        }
                    )
                else:
                    # Step 4: Propose and gate the remediation patch.
                    patch_args = {
                        "filename": ticket["affected_file"],
                        "patch_content": '{\n  "connection_timeout_ms": 5000\n}'
                    }
                    print("\n\n--- Step 4: LLM proposes a configuration patch ---")
                    patch_result = await execute_tool(
                        patch_session,
                        "Patch_Executor",
                        "apply_code_patch",
                        patch_args
                    )

                    await execute_tool(
                        sql_session,
                        "SQL_Tickets",
                        "save_patch_details",
                        {
                            "ticket_id": ticket_id,
                            "filename": patch_args["filename"],
                            "patch_content": patch_args["patch_content"],
                            "patch_result": patch_result,
                        }
                    )

                # Step 5: Generate the closing RCA prompt after remediation or escalation.
                prompt_result = await sql_session.get_prompt(
                    "incident_rca",
                    {"ticket_id": ticket_id}
                )
                prompt_text = "\n\n".join(
                    message.content.text for message in prompt_result.messages
                )
                print("\n\n--- Step 5: SQL Server returns the closing incident RCA prompt ---")
                print(prompt_text)

if __name__ == "__main__":
    args = _parse_args()
    disable_hitl = args.disable_hitl or os.getenv("MCP_DISABLE_HITL", "").lower() in {"1", "true", "yes", "on"}
    asyncio.run(run_orchestrator(disable_hitl=disable_hitl))
