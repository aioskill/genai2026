"""Generated knowledge prompting demonstration."""

from common import build_client, resolve_model


def answer_with_generated_knowledge(
    client, model: str, question: str
) -> str:
    """Answer a question using generated knowledge in two steps."""
    # Step 1: Generate Knowledge
    knowledge_response = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": (
                    "Generate 3 concise background facts or principles "
                    f"necessary to answer this question: '{question}'"
                ),
            }
        ],
    )

    generated_knowledge = knowledge_response.content[0].text
    print(f"{'=' * 100}")
    print(f"Generated knowledge: {generated_knowledge}")
    print(f"{'=' * 100}")

    # Step 2: Integrate Knowledge for Final Answer
    final_response = client.messages.create(
        model=model,
        max_tokens=512,
        system=(
            "Answer the question accurately using the provided "
            "background knowledge."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Background Knowledge:\n{generated_knowledge}\n\n"
                    f"Question: {question}"
                ),
            }
        ],
    )

    return final_response.content[0].text


def main() -> None:
    """Demonstrate generated knowledge prompting."""
    client = build_client()
    model = resolve_model()

    result = answer_with_generated_knowledge(
        client,
        model,
        "Is it safe to place a sealed glass jar full of water in the freezer?",
    )
    print("AI Answer: \n ", result)


if __name__ == "__main__":
    main()
