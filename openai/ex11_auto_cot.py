import os

from dotenv import load_dotenv
from openai import OpenAI

"""
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

load_dotenv()
DEFAULT_MODEL = os.environ["OPENAI_MODEL"]


def build_client() -> OpenAI:
    return OpenAI()


def zero_shot_cot(question: str) -> dict:
    """
    Phase 2 of Auto-CoT: Take a candidate cluster question and automatically
    generate a verified Chain-of-Thought reasoning path.
    """
    prompt = f"Question: {question}\nLet's think step by step."
    client = build_client()
    response = client.responses.create(
        model=DEFAULT_MODEL,
        instructions="You are a precise reasoning generator. Solve the problem step-by-step.",
        input=prompt
    )

    reasoning_output = getattr(response, "output_text", "")

    return {
        "user_query": question,
        "assistant_cot_response": reasoning_output
    }


# Example unlabelled question selected from a cluster center
candidate_question = (
    "A warehouse receives 3 shipments of 120 boxes each. "
    "15% of the boxes in the first shipment are damaged. "
    "How many undamaged boxes arrived in total?"
)

# Generate demonstration automatically
auto_example = zero_shot_cot(candidate_question)

print("--- AUTO-GENERATED COT EXAMPLE ---")
print(f"User: {auto_example['user_query']}\n")
print(f"Assistant:\n{auto_example['assistant_cot_response']}")