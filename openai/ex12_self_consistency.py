import os
import re
from dotenv import load_dotenv
from openai import OpenAI
from collections import Counter
"""
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

load_dotenv()
DEFAULT_MODEL = os.environ["OPENAI_MODEL"]


client = OpenAI()


def solve_with_self_consistency(prompt: str, n_samples: int = 5) -> str:
    answers = []
    # Generate N independent reasoning samples
    for _ in range(n_samples):
        response = client.responses.create(
            model="gpt-4o-mini",
            instructions=(
                "Solve the math/logic problem by writing your reasoning step-by-step. "
                "End your output with 'FINAL ANSWER: <value>'."
            ),
            input=prompt,
            temperature=0.7,  # Enable diversity across paths
        )
        output_text = getattr(response, "output_text", "")

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


# Example Query
question = ("Janet has 3 boxes of 12 pencils. She gives 1/3 to her brother "
            "and 4 pencils to her friend. How many pencils does she have left?")
result = solve_with_self_consistency(question, n_samples=5)
print(result)