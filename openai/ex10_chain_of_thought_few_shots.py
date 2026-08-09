import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
DEFAULT_MODEL = os.environ["OPENAI_MODEL"]




def build_client() -> OpenAI:
    return OpenAI()


# Example Bank (In production, stored in a Vector DB)
EXAMPLE_BANK = [
    {
        "input": "User bought item 2 hours ago, unopened, requests refund.",
        "reasoning": "1. Time window is < 14 days (2 hours).\n2. Unopened condition verified.\n3. Low fraud risk.",
        "decision": "APPROVE_AUTOMATED"
    },
    {
        "input": "User has made 8 refund claims this week across 3 accounts with gift cards.",
        "reasoning": "1. High velocity (8 refunds/week).\n2. Multiple accounts detected.\n3. Gift card payment method matches abuse pattern.",
        "decision": "FLAG_FOR_HUMAN_FRAUD_TEAM"
    }
]


def find_relevant_examples(user_request: str) -> list:
    """
    In production: Perform a vector similarity search (k=2)
    to retrieve the most relevant past cases for the current user_request.
    """
    # Returns top-k matching examples from the bank
    return EXAMPLE_BANK[:2]


def evaluate_refund_request(client, user_request: str):
    # Retrieve dynamic few-shot examples
    matched_examples = find_relevant_examples(user_request)

    # Build history items with dynamically retrieved shots
    items = []
    for ex in matched_examples:
        items.append({"role": "user", "content": ex["input"]})
        items.append({"role": "assistant", "content": f"Reasoning:\n{ex['reasoning']}\n\nDecision: {ex['decision']}"})

    # Create/seed conversation
    conversation = client.conversations.create(items=items)

    SYSTEM_PROMPT = ("You are a Refund Fraud Examiner. Reason step-by-step before making a decision.")

    # Process the active input
    response = client.responses.create(
        model=DEFAULT_MODEL,
        conversation={"id": conversation.id},
        instructions=SYSTEM_PROMPT,
        input=user_request
    )
    return response

def chat_with_felix():
    """Chat with Felix, the chatbot."""
    client = build_client()
    user_request = (
        "Customer ID #94812 (Account Age: 3 days) requests an immediate cash refund "
        "of $450 for a high-end gaming headset. They claim the package arrived empty. "
        "Tracking shows 'Delivered - Signed by Resident'. This is their 2nd empty-box "
        "claim on this new account within 72 hours."
    )
    response = evaluate_refund_request(client, user_request)
    output_text = getattr(response, "output_text", None) or "No response generated."
    print(f"Felix: \n{output_text}")


if __name__ == '__main__':
    chat_with_felix()