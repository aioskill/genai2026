"""Web search tool demonstration."""

from common import build_client, resolve_model, print_title


def main() -> None:
    """Use Claude with built-in web search tool."""
    client = build_client()
    model = resolve_model()

    print_title("Web search tool demonstration")

    # First request with web search
    response = client.messages.create(
        model=model,
        max_tokens=512,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
            }
        ],
        messages=[
            {
                "role": "user",
                "content": "What was a funny news story from today in India?",
            }
        ],
    )

    # Extract the text response
    first_text = None
    for block in response.content:
        if hasattr(block, "text"):
            first_text = block.text
            break

    if first_text:
        print("Funny news: ", first_text)

    # Follow-up question using the conversation
    conversation_messages = [
        {
            "role": "user",
            "content": "What was a funny news story from today in USA?",
        },
        {
            "role": "assistant",
            "content": response.content,
        },
        {
            "role": "user",
            "content": "Why do you find it funny?",
        },
    ]

    follow_up_response = client.messages.create(
        model=model,
        max_tokens=256,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
            }
        ],
        messages=conversation_messages,
    )

    follow_up_text = None
    for block in follow_up_response.content:
        if hasattr(block, "text"):
            follow_up_text = block.text
            break

    if follow_up_text:
        print("Why funny: ", follow_up_text)


if __name__ == "__main__":
    main()
