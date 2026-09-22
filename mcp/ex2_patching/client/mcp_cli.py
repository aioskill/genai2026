from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import AsyncExitStack
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import OpenAI
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console

load_dotenv()

console = Console()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_LOG_PATH = PROJECT_ROOT / "logs" / "cli.log"
log = logging.getLogger("sre_cli")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
DEFAULT_CONFIG = str(PROJECT_ROOT / "server" / "config.yaml")
CATEGORY_ALIASES = {
    "fleet": "fleet",
    "health": "fleet",
    "files": "files",
    "file": "files",
    "config": "config",
    "configuration": "config",
    "systemd": "systemd",
    "service": "systemd",
    "services": "systemd",
    "users": "users",
    "user": "users",
    "security": "security",
    "vulnerability": "security",
    "automation": "automation",
    "playbooks": "automation",
}
CATEGORY_PREFIXES = {
    "fleet": ("list_managed_servers", "get_system_health", "get_disk_usage"),
    "files": (
        "list_directory",
        "read_file_head_tail",
        "grep_file",
        "read_journal_logs",
        "get_activity_logs",
        "list_scheduled_tasks",
        "approve_path_access",
        "list_approved_paths",
        "revoke_path_access",
    ),
    "config": ("insert_text_block", "replace_text_regex"),
    "systemd": (
        "list_systemd_services",
        "systemd_service_exists",
        "get_service_status",
        "start_systemd_service",
        "stop_systemd_service",
        "restart_systemd_service",
        "reload_systemd_service",
        "add_systemd_service",
        "remove_systemd_service",
    ),
    "users": (
        "list_system_users",
        "get_recent_logins",
        "create_system_user",
        "disable_system_user",
        "enable_system_user",
        "remove_system_user",
    ),
    "security": (
        "scan_vulnerabilities",
        "check_cve_status",
        "patch_cve",
        "check_reboot_required",
    ),
    "automation": (
        "list_available_playbooks",
        "run_system_patching",
        "run_package_installer",
        "execute_playbook",
        "cancel_scheduled_task",
    ),
}


class McpServerUnavailable(RuntimeError):
    """Raised when the MCP server process or transport is unavailable."""


class McpSessionManager:
    """Owns the SSE connection to the MCP server and reconnects on demand."""

    def __init__(self, server_url: str) -> None:
        self.server_url = server_url
        self._stack: AsyncExitStack | None = None
        self.session: ClientSession | None = None
        self.tools: list[Any] = []
        self.connected = False

    async def connect(self) -> bool:
        await self.close()
        stack = AsyncExitStack()
        try:
            read_stream, write_stream = await stack.enter_async_context(
                sse_client(self.server_url)
            )
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            page = await session.list_tools()
            self.session = session
            self.tools = list(page.tools)
            self._stack = stack
            self.connected = True
            return True
        except asyncio.CancelledError:
            await stack.aclose()
            self.connected = False
            raise
        except Exception as exc:
            log.warning("MCP server connect failed: %s", exc)
            await stack.aclose()
            self.session = None
            self.connected = False
            return False

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        session = self.session
        if session is None:
            raise McpServerUnavailable()
        try:
            return await session.call_tool(name, arguments)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.close()
            raise McpServerUnavailable() from None

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self.session = None
        self.connected = False


DEFAULT_SYSTEM_PROMPT = (
    "You are a concise Linux SRE assistant. Use the available MCP tools for "
    "infrastructure facts. Respect dry-run, targeting, and safety errors. "
    "Ask for a server_id or tags when a tool requires a target. Never invent "
    "tool results or server details. When a tool returns PATH_OUTSIDE_SANDBOX, "
    "ask the current user for explicit permission before calling "
    "approve_path_access; never grant or retry access without the user's "
    "consent, and never attempt access to a PATH_DENIED path. Use "
    "list_approved_paths and revoke_path_access to manage granted access."
)


def json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return str(value)


def mcp_result_text(result: Any) -> str:
    if getattr(result, "is_error", False):
        return json.dumps(
            {"is_error": True, "content": getattr(result, "content", [])},
            default=json_default,
        )
    return json.dumps(result, default=json_default)


def extract_gateway_error(output: str) -> dict[str, str] | None:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return None

    def walk(value: Any) -> dict[str, str] | None:
        if isinstance(value, dict):
            if value.get("status") == "error":
                error = value.get("error")
                if isinstance(error, dict):
                    code = str(error.get("code") or "INTERNAL_ERROR")
                    message = str(error.get("message") or "MCP tool failed")
                    return {"code": code, "message": message}
            if value.get("type") == "text" and isinstance(value.get("text"), str):
                nested = walk(value["text"])
                if nested is not None:
                    return nested
            for key in ("content", "contents", "data", "results"):
                if key in value:
                    nested = walk(value[key])
                    if nested is not None:
                        return nested
        elif isinstance(value, list):
            for item in value:
                nested = walk(item)
                if nested is not None:
                    return nested
        elif isinstance(value, str):
            try:
                nested_value = json.loads(value)
            except json.JSONDecodeError:
                return None
            return walk(nested_value)
        return None

    return walk(payload)


def openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description or "MCP server tool",
            "parameters": tool.inputSchema,
        }
        for tool in mcp_tools
    ]


def extract_function_calls(response: Any) -> list[Any]:
    return [item for item in response.output if item.type == "function_call"]


def format_exception(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        messages = []
        for item in exc.exceptions:
            message = format_exception(item)
            if message and message not in messages:
                messages.append(message)
        if len(messages) == 1:
            return messages[0]
        return "; ".join(messages) if messages else str(exc)
    return str(exc)


class JsonFormatter(logging.Formatter):
    """Format CLI records as single-line JSON for log collectors."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "tool_name",
            "call_id",
            "model",
            "status",
            "duration_ms",
            "error_code",
            "error_id",
            "user_input",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    """Route CLI application logs to logs/cli.log under the project root."""
    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    logging.getLogger("mcp").propagate = False
    try:
        CLI_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            CLI_LOG_PATH, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        handler.setLevel(logging.INFO)
        handler.setFormatter(JsonFormatter())
        log.setLevel(logging.INFO)
        log.addHandler(handler)
        log.propagate = False
    except OSError:
        log.warning("Unable to open CLI log file: %s", CLI_LOG_PATH)


class InteractiveMcpClient:
    def __init__(
        self,
        manager: McpSessionManager,
        openai_client: OpenAI,
        model: str,
        system_prompt: str,
    ) -> None:
        self.manager = manager
        self.openai_client = openai_client
        self.model = model
        self.system_prompt = system_prompt
        self.tools: list[Any] = list(manager.tools)
        self.previous_response_id: str | None = None

    async def discover_tools(self) -> None:
        if self.manager.connected:
            self.tools = list(self.manager.tools)

    def describe_tools(self) -> None:
        self.print_help("all")

    def print_help(self, category: str | None = None) -> None:
        if category is None:
            console.print("\n[bold]Interactive commands:[/bold]")
            console.print("- /help [category]  Show command or category help")
            console.print("- /tools             List every discovered MCP tool")
            console.print("- /reset             Reset model conversation context")
            console.print("- /exit              Exit the client")
            console.print(
                "\nCategories: fleet, files, config, systemd, users, security, automation"
            )
            return

        normalized = category.strip().lower()
        if normalized == "all":
            selected = self.tools
            heading = "all MCP tools"
        else:
            canonical = CATEGORY_ALIASES.get(normalized)
            if canonical is None:
                console.print(
                    f"[yellow]Unknown help category: {category}. "
                    "Use /help to see available categories.[/yellow]"
                )
                return
            names = set(CATEGORY_PREFIXES[canonical])
            selected = [tool for tool in self.tools if tool.name in names]
            heading = f"{canonical} tools"

        console.print(f"\n[bold]{heading.capitalize()}:[/bold]")
        for tool in selected:
            console.print(
                f"- [cyan]{tool.name}[/cyan]: {tool.description or 'No description'}"
            )

    def ask_model(self, user_text: str) -> Any:
        request: dict[str, Any] = {
            "model": self.model,
            "instructions": self.system_prompt,
            "input": user_text,
            "tools": openai_tools(self.tools),
            "store": True,
        }
        if self.previous_response_id:
            request["previous_response_id"] = self.previous_response_id
        return self.openai_client.responses.create(**request)

    async def answer(self, user_text: str) -> str:
        response = self.ask_model(user_text)
        iterations = 0
        while True:
            self.previous_response_id = response.id
            calls = extract_function_calls(response)
            if not calls:
                answer = response.output_text or "The model returned no text."
                log.info(
                    "Model answer produced",
                    extra={
                        "model": self.model,
                        "status": "success" if response.output_text else "empty",
                    },
                )
                return answer
            iterations += 1
            if iterations > 20:
                self.previous_response_id = None
                return (
                    "I could not finish this request after several tool attempts. "
                    "The last tool error was returned to the conversation; "
                    "please refine the request or review the granted path approvals."
                )

            outputs: list[dict[str, str]] = []
            direct_error: dict[str, str] | None = None
            for call in calls:
                started = time.monotonic()
                try:
                    arguments = json.loads(call.arguments or "{}")
                    with console.status(
                        f"[bold green]Running {call.name}...", spinner="dots"
                    ):
                        result = await self.manager.call_tool(call.name, arguments)
                    output = mcp_result_text(result)
                    direct_error = extract_gateway_error(output)
                    status = (
                        "error"
                        if direct_error is not None
                        else "error"
                        if getattr(result, "is_error", False)
                        else "success"
                    )
                    log.info(
                        "Tool call completed",
                        extra={
                            "tool_name": call.name,
                            "call_id": call.call_id,
                            "status": status,
                            "duration_ms": round((time.monotonic() - started) * 1000),
                            "error_code": direct_error.get("code") if direct_error else None,
                        },
                    )
                except McpServerUnavailable:
                    raise
                except json.JSONDecodeError as exc:
                    log.error(
                        "Model returned invalid tool arguments",
                        extra={"tool_name": call.name, "error_code": "INVALID_MODEL_ARGUMENTS"},
                    )
                    output = json.dumps(
                        {
                            "is_error": True,
                            "code": "INVALID_MODEL_ARGUMENTS",
                            "message": str(exc),
                        }
                    )
                except Exception as exc:
                    log.exception(
                        "Tool call failed",
                        extra={"tool_name": call.name, "call_id": call.call_id, "error_code": "TOOL_CALL_FAILED"},
                    )
                    raise McpServerUnavailable(
                        f"MCP tool call failed for {call.name}: {format_exception(exc)}"
                    ) from exc
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": output,
                    }
                )

            if direct_error is not None and direct_error["code"] not in {
                "PATH_OUTSIDE_SANDBOX"
            }:
                # The response contains an unresolved function call. Do not
                # reuse it on the next user request after returning early.
                self.previous_response_id = None
                return f"I couldn’t complete that request because {direct_error['message']}"

            try:
                response = self.openai_client.responses.create(
                    model=self.model,
                    instructions=self.system_prompt,
                    previous_response_id=self.previous_response_id,
                    input=outputs,
                    tools=openai_tools(self.tools),
                    store=True,
                )
            except Exception:
                # The tool call has no usable output from the model's point
                # of view. Starting the next request from this response ID
                # would make the API reject it as an unresolved call.
                self.previous_response_id = None
                raise


async def interactive(
    model: str,
    system_prompt: str,
    server_url: str,
) -> None:
    manager = McpSessionManager(server_url)
    client = InteractiveMcpClient(
        manager, OpenAI(), model=model, system_prompt=system_prompt
    )
    reconnect_task: asyncio.Task | None = None

    async def reconnect_loop() -> None:
        while True:
            await asyncio.sleep(2)
            if manager.connected:
                return
            if await manager.connect():
                client.tools = list(manager.tools)
                console.print(
                    "[bold green]Assistant >>>[/bold green] Reconnected to the MCP server."
                )
                return

    def start_reconnect() -> None:
        nonlocal reconnect_task
        if reconnect_task is None or reconnect_task.done():
            reconnect_task = asyncio.create_task(reconnect_loop())

    if await manager.connect():
        client.tools = list(manager.tools)
        log.info(
            "MCP server connected",
            extra={"server_url": server_url, "model": model, "tool_count": len(client.tools)},
        )
        console.print("[bold]Interactive MCP SRE client[/bold]")
        console.print(f"Connected to server with {len(client.tools)} tools.")
    else:
        log.error("MCP server failed during startup", extra={"error_code": "MCP_STARTUP"})
        console.print(
            "[bold red]Assistant >>>[/bold red] Could not connect to the MCP server at "
            f"{server_url}.\nStart it with [cyan]./start_server.sh[/cyan] and ask again. "
            "Reconnecting in the background..."
        )
        start_reconnect()
    console.print(
        "Type /help for commands, /tools to list tools, or /exit to quit.\n"
    )

    prompt = PromptSession(
        history=FileHistory(str(PROJECT_ROOT / ".mcp_prompt_history"))
    )
    while True:
        try:
            user_text = (
                await asyncio.to_thread(prompt.prompt, "You >>> ")
            ).strip()
        except (EOFError, KeyboardInterrupt):
            user_text = "/exit"
        except Exception as exc:
            log.exception("Prompt input failed", extra={"error_code": "PROMPT_ERROR"})
            console.print(
                f"[bold red]Assistant >>>[/bold red] {format_exception(exc)}"
            )
            continue
        if not user_text:
            continue
        command = user_text.lower()
        if command in {"/exit", "/quit", "exit", "quit"}:
            log.info("CLI exited")
            return
        if command == "/tools":
            client.describe_tools()
            continue
        if command == "/help" or command.startswith("/help "):
            category = (
                user_text.split(maxsplit=1)[1] if " " in user_text else None
            )
            client.print_help(category)
            continue
        if command == "/reset":
            client.previous_response_id = None
            console.print("[yellow]Conversation context reset.[/yellow]")
            continue

        if not manager.connected:
            log.warning("User request while server unavailable", extra={"error_code": "MCP_UNAVAILABLE"})
            console.print(
                "[bold red]Assistant >>>[/bold red] The MCP server is not reachable. "
                f"Start it with [cyan]./start_server.sh[/cyan] and ask again. "
                "Reconnecting in the background..."
            )
            start_reconnect()
            continue

        try:
            log.info("User request", extra={"user_input": user_text})
            with console.status(
                "[bold green]Assistant is thinking...", spinner="dots"
            ):
                answer = await client.answer(user_text)
        except McpServerUnavailable:
            log.error("MCP server unavailable", extra={"error_code": "MCP_UNAVAILABLE"})
            console.print(
                "[bold red]Assistant >>>[/bold red] The connection to the MCP server was lost. "
                f"Start it with [cyan]./start_server.sh[/cyan] and ask again. "
                "Reconnecting in the background..."
            )
            start_reconnect()
            continue
        except ExceptionGroup as exc:
            log.error("Request failed: %s", format_exception(exc), extra={"error_code": "REQUEST_FAILED"})
            console.print(
                f"[bold red]Assistant >>>[/bold red] {format_exception(exc)}"
            )
            continue
        except Exception as exc:
            log.error("Request failed: %s", format_exception(exc), extra={"error_code": "REQUEST_FAILED"})
            console.print(
                f"[bold red]Assistant >>>[/bold red] {format_exception(exc)}"
            )
            continue
        console.print(f"\n[bold cyan]Assistant >>>[/bold cyan] {answer}\n")


@click.command()
@click.option("--config", default=DEFAULT_CONFIG, show_default=True)
@click.option("--model", default=DEFAULT_MODEL, show_default=True)
@click.option(
    "--system", "system_prompt", default=DEFAULT_SYSTEM_PROMPT, show_default=True
)
@click.option(
    "--server-url",
    default="http://127.0.0.1:8000/sse",
    show_default=True,
    help="SSE endpoint of the running MCP server.",
)
def main(config: str, model: str, system_prompt: str, server_url: str) -> None:
    """Interact with the Linux SRE MCP server through an OpenAI model."""
    configure_logging()
    log.info(
        "CLI starting",
        extra={"model": model, "config": config, "server_url": server_url},
    )
    if not os.getenv("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY is not set; aborting")
        raise click.ClickException("Set OPENAI_API_KEY before starting the client.")
    try:
        asyncio.run(interactive(model, system_prompt, server_url))
    except KeyboardInterrupt:
        log.info("CLI interrupted")
        console.print("\n[yellow]Exiting. Goodbye.[/yellow]")
    except FileNotFoundError as exc:
        log.exception("Configuration or executable not found", extra={"error_code": "FILE_NOT_FOUND"})
        raise click.ClickException(
            f"Configuration or executable not found: {exc}"
        ) from exc
    except ExceptionGroup as exc:
        log.exception("CLI failed", extra={"error_code": "EXCEPTION_GROUP"})
        raise click.ClickException(format_exception(exc)) from exc
    except Exception as exc:
        log.exception("CLI failed", extra={"error_code": "FATAL"})
        raise click.ClickException(str(exc)) from exc


if __name__ == "__main__":
    main()
