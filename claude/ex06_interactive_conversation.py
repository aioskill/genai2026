"""Interactive CLI conversation with Claude API."""

import click
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from common import build_client, resolve_model, Conversation

console = Console()

# Create a prompt session that saves history to a file
prompt_session = PromptSession(history=FileHistory('.prompt_history'))


def ask_until_exit() -> str:
    """Prompt user for input until they exit."""
    while True:
        try:
            text = prompt_session.prompt("You >>> ").strip()
            if text:
                return text
        except (click.Abort, KeyboardInterrupt):
            return "/exit"


@click.command()
@click.option(
    "--model",
    default=None,
    help="Claude model to use.",
)
@click.option(
    "--system",
    "system_prompt",
    default=(
        "You are a helpful, concise IT support assistant working inside an "
        "enterprise environment. Keep your answer short, less commentary."
    ),
    show_default=True,
    help="Instructions for the assistant.",
)
@click.option(
    "--temperature",
    default=0.0,
    show_default=True,
    help="Model temperature.",
    type=float,
)
def main(model: str, system_prompt: str, temperature: float) -> None:
    """Run an interactive conversation with Claude."""
    client = build_client()

    # Cap temperature at 1.0
    if temperature > 1.0:
        temperature = 1.0
        click.echo("Note: Temperature capped at 1.0\n")

    if not model:
        model = resolve_model()

    conversation = Conversation()

    click.echo("Interactive Claude conversation")
    click.echo("Type /history to print the stored transcript, or /exit to quit.\n")
    click.echo(f"System prompt: {system_prompt}\n")

    while True:
        user_text = ask_until_exit()
        if user_text.lower() in {"/exit", "exit", "quit"}:
            break
        if user_text.lower() == "/history":
            click.echo("\n" + "=" * 100)
            click.echo("Conversation History:")
            click.echo("=" * 100)
            turn_number = 1
            for msg in conversation.messages:
                role = msg.role.capitalize()
                if role == "Assistant":
                    label = f"{role} {turn_number}"
                    turn_number += 1
                else:
                    label = role
                click.echo(f"- {label}: {msg.content}")
            click.echo("=" * 100 + "\n")
            continue

        conversation.add_message("user", user_text)

        with console.status(
            "[bold green]Assistant is thinking...", spinner="dots"
        ):
            response = client.messages.create(
                model=model,
                max_tokens=512,
                system=system_prompt,
                temperature=temperature,
                messages=conversation.to_api_format(),
            )

            assistant_text = response.content[0].text
            conversation.add_message("assistant", assistant_text)

        click.echo(f"\nAssistant >>> {assistant_text}\n")


if __name__ == "__main__":
    main()
