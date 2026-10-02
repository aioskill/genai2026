"""Multi-turn conversation with client-side message history."""

from common import build_client, resolve_model, print_title, Conversation


def main() -> None:
    """Conduct a two-turn conversation with the model."""
    client = build_client()
    model = resolve_model()

    print_title("Multi-turn text conversation")

    conversation = Conversation()

    # First turn
    conversation.add_message(
        "user",
        (
            "Suggest a short, friendly project name for a beginner tutorial about the "
            "Claude API."
        ),
    )

    first_response = client.messages.create(
        model=model,
        max_tokens=256,
        temperature=1.2,
        messages=conversation.to_api_format(),
    )

    first_text = first_response.content[0].text
    print("Round 1:", first_text)

    # Add assistant response to history
    conversation.add_message("assistant", first_text)

    # Second turn
    conversation.add_message(
        "user",
        (
            "Make it even shorter and add a one-line subtitle for the project. "
            "Keep it text-only."
        ),
    )

    second_response = client.messages.create(
        model=model,
        max_tokens=256,
        temperature=1.2,
        messages=conversation.to_api_format(),
    )

    second_text = second_response.content[0].text
    print("\nRound 2:")
    print(second_text)


if __name__ == "__main__":
    main()
