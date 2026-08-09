from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()
DEFAULT_MODEL = os.environ["OPENAI_MODEL"]

def build_client() -> OpenAI:
    return OpenAI()


def resolve_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def print_title(title: str) -> None:
    print(f"\n=== {title} ===")


client = build_client()
model = resolve_model()

print_title("Basic text response")

response = client.responses.create(
    model=model,
    input=(
        "Explain the difference between temperature and top_p in 4 short sentences. "
        "Keep the answer text-only."
    ),
    text={"verbosity": "medium", "format": "text"},
)

print(response.output_text)
