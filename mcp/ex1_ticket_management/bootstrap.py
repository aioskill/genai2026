import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from models import SourceFile

SERVERS = {
    "SQL_Tickets": "http://localhost:8001/sse",
    "Chroma_Resolutions": "http://localhost:8002/sse",
    "Patch_Executor": "http://localhost:8003/sse",
}

TICKETS = [
    {
        "id": "TICK-201",
        "title": (
            "Users continue receiving 429 responses after their request "
            "window expires"
        ),
        "description": (
            "Several customers report that requests remain rate-limited "
            "longer than the configured 60-second rolling window. The "
            "behavior affects requests from the same user while other users "
            "continue to receive responses normally. Expired request entries "
            "should no longer count toward that user's quota."
        ),
        "applications": [
            {
                "application_name": "api-gateway",
                "host_name": "localhost",
            },
            {
                "application_name": "rate-limiter",
                "host_name": "localhost",
            },
        ],
        "status": "OPEN",
        "error_code": "ERR_RATE_LIMIT_WINDOW",
    },
]

RESOLUTIONS = [
    {
        "doc_id": "res_1",
        "document": (
            "A rolling-window limiter returned intermittent 429 responses "
            "because its timestamp cleanup retained expired request entries. "
            "Compare each request timestamp with the configured window and "
            "retain only entries that are still inside the window."
        ),
        "error_code": "ERR_RATE_LIMIT_WINDOW",
        "resolution_id": "RES-301",
    },
]

SOURCE_FILES = [
    SourceFile(
        application_name="rate-limiter",
        filename="api/rate_limit.py",
        content=(
            "from collections import defaultdict\n"
            "from threading import Lock\n"
            "from time import monotonic\n"
            "\n"
            "WINDOW_SECONDS = 60\n"
            "MAX_REQUESTS = 100\n"
            "_requests_by_user: dict[str, list[float]] = defaultdict(list)\n"
            "_state_lock = Lock()\n"
            "\n"
            "\n"
            "def is_rate_limited(user_id: str) -> bool:\n"
            "    now = monotonic()\n"
            "    with _state_lock:\n"
            "        recent_requests = [\n"
            "            request_time\n"
            "            for request_time in _requests_by_user[user_id]\n"
            "            if now - request_time > WINDOW_SECONDS\n"
            "        ]\n"
            "        _requests_by_user[user_id] = recent_requests\n"
            "        if len(recent_requests) >= MAX_REQUESTS:\n"
            "            return True\n"
            "        recent_requests.append(now)\n"
            "        return False\n"
        ),
    ),
    SourceFile(
        application_name="api-gateway",
        filename="api/gateway.py",
        content=(
            "def handle_request(request, rate_limit_client,\n"
            "                  process_request):\n"
            "    user_id = request[\"user_id\"]\n"
            "    if rate_limit_client.is_rate_limited(user_id):\n"
            "        return {\"status\": 429, \"error\": "
            "\"Too Many Requests\"}\n"
            "    return process_request(request)\n"
        ),
    ),
]


def _validate_reset_tools(
    sql_tool_names: list[str],
    chroma_tool_names: list[str],
    patch_tool_names: list[str],
) -> None:
    missing_tools = []
    if "clear_all_records" not in sql_tool_names:
        missing_tools.append("clear_all_records on SQL_Tickets")
    if "clear_all_resolutions" not in chroma_tool_names:
        missing_tools.append("clear_all_resolutions on Chroma_Resolutions")
    if "reset_source_workspace" not in patch_tool_names:
        missing_tools.append("reset_source_workspace on Patch_Executor")
    if "list_source_files" not in patch_tool_names:
        missing_tools.append("list_source_files on Patch_Executor")
    if "get_current_file" not in patch_tool_names:
        missing_tools.append("get_current_file on Patch_Executor")
    if missing_tools:
        missing = ", ".join(missing_tools)
        raise RuntimeError(
            f"MCP servers are stale: missing {missing}. Restart "
            "server_sql.py, server_chroma.py, and server_patch.py, then "
            "rerun the client."
        )


def _raise_for_tool_error(result, tool_name: str) -> None:
    if not result.isError:
        return
    error_text = "\n".join(
        getattr(content, "text", str(content))
        for content in result.content
    )
    raise RuntimeError(f"Bootstrap tool {tool_name} failed: {error_text}")


async def run_bootstrap():
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

            sql_tools, chroma_tools, patch_tools = await asyncio.gather(
                sql_session.list_tools(),
                chroma_session.list_tools(),
                patch_session.list_tools(),
            )
            _validate_reset_tools(
                [tool.name for tool in sql_tools.tools],
                [tool.name for tool in chroma_tools.tools],
                [tool.name for tool in patch_tools.tools],
            )

            print(
                "Clearing SQL and Chroma records and resetting the source "
                "workspace..."
            )
            sql_reset = await sql_session.call_tool("clear_all_records", {})
            _raise_for_tool_error(sql_reset, "clear_all_records")
            chroma_reset = await chroma_session.call_tool(
                "clear_all_resolutions",
                {},
            )
            _raise_for_tool_error(chroma_reset, "clear_all_resolutions")
            source_reset = await patch_session.call_tool(
                "reset_source_workspace",
                {
                    "files": [
                        source_file.model_dump()
                        for source_file in SOURCE_FILES
                    ],
                },
            )
            _raise_for_tool_error(source_reset, "reset_source_workspace")
            print(
                "  SQL reset -> ",
                sql_reset.content[0].text if sql_reset.content else "cleared",
            )
            print(
                "  Chroma reset -> ",
                chroma_reset.content[0].text
                if chroma_reset.content
                else "cleared",
            )
            print(
                "  Source workspace reset -> ",
                source_reset.content[0].text
                if source_reset.content
                else "reset",
            )

            print("Adding SQL ticket records...")
            for ticket in TICKETS:
                result = await sql_session.call_tool(
                    "add_ticket",
                    {"ticket": ticket},
                )
                output = (
                    result.content[0].text
                    if result.content
                    else result.content
                )
                print(
                    f"  add_ticket({ticket['id']}) -> {output}"
                )

            print("\nUpserting Chroma resolution records...")
            for resolution in RESOLUTIONS:
                result = await chroma_session.call_tool(
                    "upsert_resolution",
                    resolution,
                )
                output = (
                    result.content[0].text
                    if result.content
                    else result.content
                )
                print(
                    f"  upsert_resolution({resolution['doc_id']}) -> {output}"
                )

            print("\nBootstrapping complete.")


if __name__ == "__main__":
    asyncio.run(run_bootstrap())
