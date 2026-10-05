"""Multi-turn conversation with client-side history management."""

from common import build_client, resolve_model, Conversation


def print_turn(label: str, text: str) -> None:
    """Print a turn in the conversation."""
    print(f"{label}: {text}\n")


def run_chat_session() -> None:
    """Run an IT support chat session."""
    client = build_client()
    model = resolve_model()

    print("Initializing AI Support Session...")

    system_message = (
        "You are a helpful, concise IT support assistant. "
        "Produce text in plain text; no markdown."
    )
    conversation = Conversation()

    # Initial user message
    conversation.add_message(
        "user",
        "Hi, my office printer (Model X-200) is flashing a red light and won't print.",
    )
    print("\n" + "=" * 100)
    print("Initial message sent to assistant")
    print("=" * 100 + "\n")

    # First turn
    response = client.messages.create(
        model=model,
        max_tokens=256,
        system=system_message,
        messages=conversation.to_api_format(),
    )

    first_turn_text = response.content[0].text
    conversation.add_message("assistant", first_turn_text)
    print_turn("AI", first_turn_text)

    # Second turn
    conversation.add_message(
        "user",
        "I already tried restarting it, but the light is still flashing. What next?",
    )

    response = client.messages.create(
        model=model,
        max_tokens=256,
        system=system_message,
        messages=conversation.to_api_format(),
    )

    second_turn_text = response.content[0].text
    conversation.add_message("assistant", second_turn_text)
    print_turn("AI", second_turn_text)

    # Print conversation history
    print("=" * 100)
    print("Conversation History:")
    print("=" * 100)
    turn_number = 1
    for msg in conversation.messages:
        role = msg.role.capitalize()
        if role == "Assistant":
            label = f"{role} {turn_number}"
            turn_number += 1
        else:
            label = role
        print(f"- {label}: {msg.content}")

    print("\nConversation complete.")


if __name__ == "__main__":
    run_chat_session()
