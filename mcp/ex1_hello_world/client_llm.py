from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path.cwd() / "demo_workspace"
CASE_DIR = "cases/llm-investigation-2026-08-12"

PROBLEM = """You are a support analyst working inside an MCP-enabled workspace.

Your job:
1. Find the investigation folder under `cases`.
2. Inspect the supporting files inside that folder.
3. Combine the evidence into one concise customer-facing briefing.

Rules:
- Do not answer until you have gathered evidence from more than one file.
- You must include the outstanding invoice balance, the shipment ETA, and both contact emails.
- If a file is missing, say what is missing and continue with the other files.

Return the final answer in exactly 4 bullet points:
- case summary
- billing status
- shipping status
- contacts
"""


def text_from_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", block)))
            else:
                text = getattr(block, "text", None)
                parts.append(text if text is not None else str(block))
        return "".join(parts)

    return str(content)


def summarize_tool_message(message: Any) -> str:
    name = getattr(message, "name", None) or getattr(message, "tool_name", None) or "tool"
    content = text_from_message_content(getattr(message, "content", message))
    return f"{name}: {content.strip()}"


async def seed_workspace(session: ClientSession) -> None:
    await session.call_tool("make_directory", {"path": CASE_DIR})
    await session.call_tool(
        "write_text_file",
        {
            "path": f"{CASE_DIR}/overview.txt",
            "content": (
                "Customer reports an unpaid invoice and a delayed shipment.\n"
                "The analyst must gather billing, shipping, and contact data before replying.\n"
            ),
        },
    )
    await session.call_tool(
        "write_text_file",
        {
            "path": f"{CASE_DIR}/billing.txt",
            "content": "Invoice #8842 total: $120.00. Paid: $80.00. Outstanding: $40.00.\n",
        },
    )
    await session.call_tool(
        "write_text_file",
        {
            "path": f"{CASE_DIR}/shipping.txt",
            "content": (
                "Shipment ZX-19 left the warehouse on Aug 10, 2026.\n"
                "It is delayed at the local hub. New ETA: Aug 14, 2026.\n"
            ),
        },
    )
    await session.call_tool(
        "write_text_file",
        {
            "path": f"{CASE_DIR}/contacts.txt",
            "content": (
                "Billing contact: billing@example.com\n"
                "Shipping contact: shipping@example.com\n"
            ),
        },
    )


async def run() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        raise RuntimeError("Set OPENAI_API_KEY before running client_llm.py")

    server_params = StdioServerParameters(
        command="uv",
        args=["run", "server.py"],
        env={**os.environ, "MCP_FS_ROOT": str(ROOT)},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await seed_workspace(session)

            tools = await load_mcp_tools(session)
            model = ChatOpenAI(
                model=os.environ.get("OPENAI_MODEL", "gpt-4.1"),
                temperature=0,
                api_key=openai_key,
            )
            agent = create_agent(model, tools=tools)

            result = await agent.ainvoke({"messages": [{"role": "user", "content": PROBLEM}]})

            messages = result["messages"]
            print("Agent trace:")
            for message in messages:
                msg_type = getattr(message, "type", message.__class__.__name__)
                if msg_type in {"ai", "tool", "human"}:
                    print(f"- {msg_type}: {text_from_message_content(getattr(message, 'content', message)).strip()}")

            print("\nFinal answer:")
            print(text_from_message_content(getattr(messages[-1], "content", messages[-1])).strip())


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
