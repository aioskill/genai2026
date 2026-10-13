"""Show automatic prompt caching with a reusable product catalog."""

import os

from dotenv import load_dotenv
from openai import OpenAI


def build_catalog() -> str:
    """Build stable shared context long enough to be cacheable."""
    products = []
    for product_id in range(1, 121):
        products.append(
            f"Product {product_id:03}: reusable stainless steel "
            "water bottle; "
            f"capacity {400 + product_id * 10} ml; "
            f"color option {product_id % 8}."
        )
    return "\n".join(products)


def print_cached_tokens(response, request_number: int) -> None:
    usage = response.usage
    details = usage.input_tokens_details if usage else None
    cached_tokens = details.cached_tokens if details else 0
    print(f"Request {request_number} cached input tokens: {cached_tokens}")


def main() -> None:
    load_dotenv()
    client = OpenAI()
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    catalog = build_catalog()

    questions = [
        "Which product has the largest capacity? "
        "Answer with its ID and capacity.",
        "Which product has the smallest capacity? "
        "Answer with its ID and capacity.",
    ]

    for request_number, question in enumerate(questions, start=1):
        response = client.responses.create(
            model=model,
            instructions=(
                "You are a concise product catalog assistant. "
                "Use only the supplied "
                "catalog when answering.\n\nCatalog:\n"
                f"{catalog}"
            ),
            input=question,
        )
        print(
            f"\nAnswer {request_number}: {response.output_text}"
        )
        print_cached_tokens(response, request_number)


if __name__ == "__main__":
    main()
