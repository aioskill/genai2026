"""Streaming text response demonstration."""

from common import build_client, resolve_model, print_title


def main() -> None:
    """Stream a response about learning Claude API."""
    client = build_client()
    model = resolve_model()

    print_title("Streaming text response")

    with client.messages.stream(
        model=model,
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": (
                    "Write a 6-line checklist for learning the Claude API. "
                    "Text only, no markdown tables."
                ),
            }
        ],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)

    print()


if __name__ == "__main__":
    main()
