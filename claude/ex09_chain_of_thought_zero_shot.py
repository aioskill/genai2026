"""Zero-shot chain of thought demonstration."""

from common import build_client, resolve_model


def main() -> None:
    """Demonstrate zero-shot chain of thought reasoning."""
    client = build_client()
    model = resolve_model()

    system_instruction = (
        "Think step by step. In the output include the reasoning in bullets. "
        "Provide the output as raw, unformatted text."
    )

    user_request = """
        When James was 2 years old, his sister was 4 years old. James is now
        30 years old. How old is his sister?
    """

    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=system_instruction,
        messages=[
            {
                "role": "user",
                "content": user_request,
            }
        ],
    )

    response_text = response.content[0].text
    print(f"AI: \n{response_text}")


if __name__ == "__main__":
    main()
