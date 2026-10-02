"""Self-consistency demonstration with majority voting."""

import re
from collections import Counter
from common import build_client, resolve_model

# Diagram for reference
PHASE_DIAGRAM = """
────────────────────────────────────────────────────────┐
│                   1. CoT Prompting                    │
│  Prompt model with a question using Chain-of-Thought. │
└───────────────────────────┬───────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│              2. Sample Multiple Paths                  │
│  Generate N responses (e.g., N=5) with temperature > 0 │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                  3. Majority Voting                    │
│  Extract final answers & pick the most frequent answer │
└────────────────────────────────────────────────────────┘
"""


def solve_with_self_consistency(
    client, model: str, prompt: str, n_samples: int = 5
) -> str:
    """Generate multiple reasoning paths and return the majority vote."""
    answers = []

    # Generate N independent reasoning samples
    for _ in range(n_samples):
        response = client.messages.create(
            model=model,
            max_tokens=512,
            temperature=0.7,
            system=(
                "Solve the math/logic problem by writing your reasoning "
                "step-by-step. End your output with 'FINAL ANSWER: <value>'."
            ),
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        output_text = response.content[0].text

        # Extract final answer using regex
        match = re.search(r"FINAL ANSWER:\s*(.+)", output_text, re.IGNORECASE)
        if match:
            answers.append(match.group(1).strip())

    # Perform majority voting
    if not answers:
        return "No valid final answers extracted."

    vote_counts = Counter(answers)
    most_common_answer, count = vote_counts.most_common(1)[0]

    print(f"Votes distribution: {dict(vote_counts)}")
    return f"Consensus Answer: {most_common_answer} ({count}/{len(answers)} votes)"


def main() -> None:
    """Demonstrate self-consistency with multiple reasoning paths."""
    client = build_client()
    model = resolve_model()

    print(PHASE_DIAGRAM)

    # Example Query
    question = (
        "Janet has 3 boxes of 12 pencils. She gives 1/3 to her brother "
        "and 4 pencils to her friend. How many pencils does she have left?"
    )

    result = solve_with_self_consistency(client, model, question, n_samples=5)
    print(result)


if __name__ == "__main__":
    main()
