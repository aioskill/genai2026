"""Few-shot learning demonstration (version 1)."""

from common import build_client, resolve_model, Conversation


def make_request(client, conversation: Conversation, message: str, model: str):
    """Make a request to Claude with the current conversation."""
    conversation.add_message("user", message)

    response = client.messages.create(
        model=model,
        max_tokens=256,
        temperature=1.0,
        messages=conversation.to_api_format(),
    )

    response_text = response.content[0].text
    conversation.add_message("assistant", response_text)
    return response_text


def chat_with_felix() -> None:
    """Chat with Felix, demonstrating few-shot learning."""
    client = build_client()
    model = resolve_model()

    # Initialize conversation with few-shot examples
    conversation = Conversation()

    # Add examples to teach the pattern
    conversation.add_message("user", "1")
    conversation.add_message("assistant", "X")
    conversation.add_message("user", "2")
    conversation.add_message("assistant", "Y")

    # Now test with new inputs
    for message in ("3", "4", "alpha"):
        response_text = make_request(client, conversation, message, model)
        print(f"User: {message}, AI: {response_text}")


if __name__ == "__main__":
    chat_with_felix()
