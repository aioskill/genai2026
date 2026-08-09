from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()
DEFAULT_MODEL = os.environ["OPENAI_MODEL"]



def build_client() -> OpenAI:
    return OpenAI()


def resolve_model() -> str:
    import os
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def print_title(title: str) -> None:
    print(f"\n=== {title} ===")


client = build_client()
model = resolve_model()

print_title("Streaming text response")

with client.responses.stream(
    model=model,
    input=(
        "Write a 6-line checklist for learning the OpenAI Responses API. "
        "Text only, no markdown tables."
    ),
) as stream:
    for event in stream:
        if event.type == "response.output_text.delta":
            print(event.delta, end="", flush=True)

print()
