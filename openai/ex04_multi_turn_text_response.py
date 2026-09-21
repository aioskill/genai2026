from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()
# DEFAULT_MODEL = os.environ["OPENAI_MODEL"]
DEFAULT_MODEL = "gpt-4o-mini"
# DEFAULT_MODEL = "gpt-4o"


def build_client() -> OpenAI:
    load_dotenv()
    return OpenAI()

def print_title(title: str) -> None:
    print(f"\n=== {title} ===")


client = build_client()
model = DEFAULT_MODEL

print_title("Multi-turn text conversation")

first = client.responses.create(
    model=model,
    input=(
        "Suggest a short, friendly project name for a beginner tutorial about the "
        "OpenAI Responses API."
    ),
    temperature = 1.2
)
print("Round 1:", first.output_text)

follow_up = client.responses.create(
    model=model,
    previous_response_id=first.id,
    input=(
        "Make it even shorter and add a one-line subtitle for the project. "
        "Keep it text-only."
    ),
    temperature = 1.2
)

print("\nRound 2:")
print(follow_up.output_text)
