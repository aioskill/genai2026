from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()
DEFAULT_MODEL = os.environ["OPENAI_MODEL"]


def build_client() -> OpenAI:
    load_dotenv()
    return OpenAI()


def resolve_model() -> str:
    import os

    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def print_title(title: str) -> None:
    print(f"\n=== {title} ===")


client = build_client()
model = resolve_model()

print_title("Multi-turn text conversation")

first = client.responses.create(
    model=model,
    input=(
        "Suggest a short, friendly project name for a beginner tutorial about the "
        "OpenAI Responses API."
    ),
)
print("Round 1:")
print(first.output_text)

follow_up = client.responses.create(
    model=model,
    previous_response_id=first.id,
    input=(
        "Make it even shorter and add a one-line subtitle for the project. "
        "Keep it text-only."
    ),
)

print("\nRound 2:")
print(follow_up.output_text)
