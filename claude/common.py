"""Shared utilities for Claude API demonstration scripts."""

from dotenv import load_dotenv
from anthropic import Anthropic
from pydantic import BaseModel
import os


def build_client() -> Anthropic:
    """Build and return an Anthropic client."""
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    return Anthropic(api_key = api_key)


def resolve_model() -> str:
    """Resolve the model name from environment variables.

    Raises:
        ValueError: If ANTHROPIC_MODEL is not set in the environment.
    """
    load_dotenv()
    model = os.getenv("ANTHROPIC_MODEL")
    if not model:
        raise ValueError(
            "ANTHROPIC_MODEL environment variable is not set. "
            "Please set it in your .env file."
        )
    return model


def print_title(title: str) -> None:
    """Print a formatted title."""
    print(f"\n=== {title} ===")


class MessageContent(BaseModel):
    """A single message in a conversation."""
    role: str
    content: str


class Conversation(BaseModel):
    """A conversation with a list of messages."""
    messages: list[MessageContent] = []

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation."""
        self.messages.append(MessageContent(role=role, content=content))

    def to_api_format(self) -> list[dict]:
        """Convert messages to the format expected by the Anthropic API."""
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]
