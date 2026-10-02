"""Few-shot chain of thought demonstration for refund evaluation."""

from common import build_client, resolve_model, Conversation


# Example Bank (In production, stored in a Vector DB)
EXAMPLE_BANK = [
    {
        "input": "User bought item 2 hours ago, unopened, requests refund.",
        "reasoning": (
            "1. Time window is < 14 days (2 hours).\n"
            "2. Unopened condition verified.\n"
            "3. Low fraud risk."
        ),
        "decision": "APPROVE_AUTOMATED"
    },
    {
        "input": (
            "User has made 8 refund claims this week "
            "across 3 accounts with gift cards."
        ),
        "reasoning": (
            "1. High velocity (8 refunds/week).\n"
            "2. Multiple accounts detected.\n"
            "3. Gift card payment method matches abuse pattern."
        ),
        "decision": "FLAG_FOR_HUMAN_FRAUD_TEAM"
    }
]


def find_relevant_examples(user_request: str) -> list:
    """Retrieve relevant examples from the example bank."""
    # In production: Perform a vector similarity search (k=2)
    # to retrieve the most relevant past cases for the current user_request.
    # Returns top-k matching examples from the bank
    return EXAMPLE_BANK[:2]


def evaluate_refund_request(client, user_request: str, model: str):
    """Evaluate a refund request using few-shot chain of thought."""
    # Retrieve dynamic few-shot examples
    matched_examples = find_relevant_examples(user_request)

    # Build conversation with dynamically retrieved examples
    conversation = Conversation()
    for ex in matched_examples:
        conversation.add_message("user", ex["input"])
        reasoning = ex["reasoning"]
        decision = ex["decision"]
        reasoning_and_decision = f"Reasoning:\n{reasoning}\n\nDecision: {decision}"
        conversation.add_message("assistant", reasoning_and_decision)

    system_prompt = (
        "You are a Refund Fraud Examiner. Reason step-by-step before "
        "making a decision. Produce the output in plain text without any "
        "markdown notations."
    )

    # Add the current request
    conversation.add_message("user", user_request)

    # Get response from Claude
    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=system_prompt,
        messages=conversation.to_api_format(),
    )

    return response


def main() -> None:
    """Evaluate a sample refund request."""
    client = build_client()
    model = resolve_model()

    user_request = (
        "Customer ID #94812 (Account Age: 3 days) requests an immediate cash refund "
        "of $450 for a high-end gaming headset. They claim the package arrived empty. "
        "Tracking shows 'Delivered - Signed by Resident'. This is their 2nd empty-box "
        "claim on this new account within 72 hours."
    )

    response = evaluate_refund_request(client, user_request, model)
    output_text = response.content[0].text
    print(f"Felix: \n{output_text}")


if __name__ == "__main__":
    main()
