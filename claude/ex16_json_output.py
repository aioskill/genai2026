"""JSON output demonstration."""

from common import build_client, resolve_model, print_title


def main() -> None:
    """Generate JSON output with 3 primary colors and their hex codes."""
    client = build_client()
    model = resolve_model()

    print_title("JSON output")

    response = client.messages.create(
        model=model,
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": (
                    "List 3 primary colors with their hex codes. Write the response "
                    "in valid JSON format."
                ),
            }
        ],
    )

    response_text = response.content[0].text
    print(response_text)


if __name__ == "__main__":
    main()
