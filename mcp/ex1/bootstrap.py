import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

SERVERS = {
    "SQL_Tickets": "http://localhost:8001/sse",
    "Chroma_Resolutions": "http://localhost:8002/sse",
}

TICKETS = [
    {"id": "TICK-103", "title": "API returns 429 too many requests", "status": "OPEN", "error_code": "ERR_RATE_LIMIT", "affected_file": "api_gateway.py"},
    {"id": "TICK-104", "title": "Background job hangs on large exports", "status": "OPEN", "error_code": "ERR_JOB_STALL", "affected_file": "exporter.py"},
]

RESOLUTIONS = [
    {"doc_id": "res_4", "document": "ERR_RATE_LIMIT resolved by enabling token bucket throttling in api_gateway.py.", "error_code": "ERR_RATE_LIMIT", "resolution_id": "RES-204"},
    {"doc_id": "res_5", "document": "ERR_JOB_STALL resolved by adding a heartbeat timeout to the background exporter.", "error_code": "ERR_JOB_STALL", "resolution_id": "RES-205"},
]


async def run_bootstrap():
    async with sse_client(SERVERS["SQL_Tickets"]) as (r1, w1), \
            sse_client(SERVERS["Chroma_Resolutions"]) as (r2, w2):

        async with ClientSession(r1, w1) as sql_session, \
                ClientSession(r2, w2) as chroma_session:

            await asyncio.gather(
                sql_session.initialize(),
                chroma_session.initialize(),
            )

            print("Adding SQL ticket records...")
            for ticket in TICKETS:
                result = await sql_session.call_tool("add_ticket", {"ticket": ticket})
                output = result.content[0].text if result.content else result.content
                print(f"  add_ticket({ticket['id']}) -> {output}")

            print("\nUpserting Chroma resolution records...")
            for resolution in RESOLUTIONS:
                result = await chroma_session.call_tool("upsert_resolution", resolution)
                output = result.content[0].text if result.content else result.content
                print(f"  upsert_resolution({resolution['doc_id']}) -> {output}")

            print("\nBootstrapping complete.")


if __name__ == "__main__":
    asyncio.run(run_bootstrap())
