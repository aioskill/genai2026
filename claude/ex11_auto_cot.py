"""Auto Chain-of-Thought demonstration."""

from common import build_client, resolve_model

# Diagram for reference
PHASE_DIAGRAM = """
┌────────────────────────────────────────────────────────┐
│             PHASE 1: Diversity Clustering              │
│  Partition dataset of questions into K clusters using  │
│  sentence embeddings (e.g., K-Means).                  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│          PHASE 2: Auto-Generation & Pruning            │
│  1. Pick representative central question from cluster. │
│  2. Prompt LLM with Zero-Shot CoT ("Let's think...").  │
│  3. Filter out candidates with errors or bad syntax.   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                 Construct Final Prompt                 │
│  Assemble 1 high-quality CoT example per cluster.      │
└────────────────────────────────────────────────────────┘
"""


def zero_shot_cot(client, question: str, model: str) -> dict:
    """
    Phase 2 of Auto-CoT: Take a candidate cluster question and automatically
    generate a verified Chain-of-Thought reasoning path.
    """
    prompt = f"Question: {question}\nLet's think step by step."

    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=(
            "You are a precise reasoning generator. "
            "Solve the problem step-by-step. "
            "Produce plain text output (no markdown)."
        ),
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    reasoning_output = response.content[0].text

    return {
        "user_query": question,
        "assistant_cot_response": reasoning_output
    }


def main() -> None:
    """Generate an auto-CoT example."""
    client = build_client()
    model = resolve_model()

    print(PHASE_DIAGRAM)

    # Example unlabelled question selected from a cluster center
    candidate_question = (
        "A warehouse receives 3 shipments of 120 boxes each. "
        "15% of the boxes in the first shipment are damaged. "
        "How many undamaged boxes arrived in total?"
    )

    # Generate demonstration automatically
    auto_example = zero_shot_cot(client, candidate_question, model)

    print("\n--- AUTO-GENERATED COT EXAMPLE ---")
    print(f"User: {auto_example['user_query']}\n")
    print(f"Assistant:\n{auto_example['assistant_cot_response']}")


if __name__ == "__main__":
    main()
