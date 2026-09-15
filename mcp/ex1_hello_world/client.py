from __future__ import annotations

import asyncio
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path.cwd() / "demo_workspace"


def format_result(result: object) -> str:
    return repr(result)


def result_text(result: object) -> str:
    content = getattr(result, "content", None)
    if isinstance(content, list):
        return "".join(getattr(item, "text", str(item)) for item in content)
    return str(content if content is not None else result)


async def run() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    case_dir = "cases/incident-2026-08-12"

    server_params = StdioServerParameters(
        command="uv",
        args=["run", "server.py"],
        env={**os.environ, "MCP_FS_ROOT": str(ROOT)},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Available tools:")
            for tool in tools.tools:
                print(f" - {tool.name}")

            print("\nSeeding an investigation workspace...")
            print(format_result(await session.call_tool("make_directory", {"path": case_dir})))
            print(
                format_result(
                    await session.call_tool(
                        "write_text_file",
                        {
                            "path": f"{case_dir}/overview.txt",
                            "content": (
                                "Customer reports an unpaid invoice and a delayed shipment.\n"
                                "Answer must include both billing and shipping status.\n"
                            ),
                        },
                    )
                )
            )
            print(
                format_result(
                    await session.call_tool(
                        "write_text_file",
                        {
                            "path": f"{case_dir}/billing.txt",
                            "content": "Invoice #8842 total: $120.00. Paid: $80.00. Outstanding: $40.00.\n",
                        },
                    )
                )
            )
            print(
                format_result(
                    await session.call_tool(
                        "write_text_file",
                        {
                            "path": f"{case_dir}/shipping.txt",
                            "content": (
                                "Shipment ZX-19 left the warehouse on Aug 10, 2026.\n"
                                "It is delayed at the local hub. New ETA: Aug 14, 2026.\n"
                            ),
                        },
                    )
                )
            )
            print(
                format_result(
                    await session.call_tool(
                        "write_text_file",
                        {
                            "path": f"{case_dir}/contacts.txt",
                            "content": (
                                "Billing contact: billing@example.com\n"
                                "Shipping contact: shipping@example.com\n"
                            ),
                        },
                    )
                )
            )

            print("\nCollecting context with multiple tool calls...")
            print(format_result(await session.call_tool("list_directory", {"path": "."})))
            print(format_result(await session.call_tool("list_directory", {"path": "cases"})))
            print(format_result(await session.call_tool("list_directory", {"path": case_dir})))

            overview = await session.call_tool("read_text_file", {"path": f"{case_dir}/overview.txt"})
            billing = await session.call_tool("read_text_file", {"path": f"{case_dir}/billing.txt"})
            shipping = await session.call_tool("read_text_file", {"path": f"{case_dir}/shipping.txt"})
            contacts = await session.call_tool("read_text_file", {"path": f"{case_dir}/contacts.txt"})

            print("\nFinal briefing:")
            briefing_text = "\n".join(
                [
                    result_text(overview).strip(),
                    result_text(billing).strip(),
                    result_text(shipping).strip(),
                    result_text(contacts).replace("\n", " | ").strip(),
                ]
            )
            print(" - " + result_text(overview).strip())
            print(" - " + result_text(billing).strip())
            print(" - " + result_text(shipping).strip())
            print(" - " + result_text(contacts).replace("\n", " | ").strip())

            print(format_result(await session.call_tool("write_text_file", {"path": "briefing.txt", "content": briefing_text + "\n"})))

            resource = await session.read_resource("resource://briefing")
            print("\nReference resource:")
            print(format_result(resource))


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
