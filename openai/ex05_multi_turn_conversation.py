from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()
DEFAULT_MODEL = os.environ["OPENAI_MODEL"]

"""
API reference: https://developers.openai.com/api/reference/python/resources/conversations

"""

def build_client() -> OpenAI:
    load_dotenv()
    return OpenAI()


def print_turn(label: str, text: str) -> None:
    print(f"{label}: {text}\n")


def extract_text(item) -> str:
    content = getattr(item, "content", None)
    if content:
        parts = []
        for chunk in content:
            text = getattr(chunk, "text", None)
            if text is None and isinstance(chunk, dict):
                text = chunk.get("text")
            if text:
                parts.append(text)
        if parts:
            return " ".join(parts)

    return getattr(item, "output_text", None) or getattr(item, "input_text", None) or ""


def print_conversation_history(client: OpenAI, conversation_id: str) -> None:
    print("=" * 100)
    print(f"Conversation history for {conversation_id}:")
    print("="*100)
    page = client.conversations.items.list(conversation_id=conversation_id, limit=100, order="asc")
    turn_number = 1

    while True:
        for item in page.data:
            role = getattr(item, "role", None)
            if role not in {"user", "assistant"}:
                continue
            text = extract_text(item)
            if text:
                label = f"{role.capitalize()} {turn_number}"
                print(f"- {label}: {text}")
                if role == "assistant":
                    turn_number += 1

        if not page.has_more:
            break

        page = client.conversations.items.list(
            conversation_id=conversation_id,
            after=page.last_id,
            limit=100,
            order="asc",
        )


def run_chat_session() -> None:
    client = build_client()

    print("Initializing AI Support Session...")

    conversation = client.conversations.create(
        metadata={"topic": "printer-support-demo"},
        items=[
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Hi, my office printer (Model X-200) is flashing a red light and won't print."}],
            }
        ],
    )
    print(f"Conversation created: {conversation.id}\n")

    first_turn = client.responses.create(
        model=DEFAULT_MODEL,
        conversation={"id": conversation.id},
        instructions="You are a helpful, concise IT support assistant.",
        input="Diagnose the printer issue and give the next step.",
    )
    print_turn("AI", first_turn.output_text)

    second_turn = client.responses.create(
        model=DEFAULT_MODEL,
        conversation={"id": conversation.id},
        instructions="You are a helpful, concise IT support assistant.",
        input="I already tried restarting it, but the light is still flashing. What next?",
    )
    print_turn("AI", second_turn.output_text)

    print_conversation_history(client, conversation.id)
    print("Conversation complete.")


if __name__ == "__main__":
    run_chat_session()
