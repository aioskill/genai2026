"""Basic text response demonstrating temperature and top_p parameters."""

from common import build_client, resolve_model, print_title


def main() -> None:
    """Explain the difference between temperature and top_p."""
    client = build_client()
    model = resolve_model()

    print_title("Basic text response")

    response = client.messages.create(
        model=model,
        max_tokens=256,
        temperature=0.7,
        messages=[
            {
                "role": "user",
                "content": (
                    "Explain the difference between temperature and top_p in "
                    "4 short sentences. Keep the answer text-only."
                ),
            }
        ],
    )

    text_response = response.content[0].text
    print(text_response)


if __name__ == "__main__":
    main()
