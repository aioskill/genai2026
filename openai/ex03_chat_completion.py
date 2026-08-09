from __future__ import annotations
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

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

print_title("Structured text output")

schema = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "level": {
            "type": "string",
            "enum": ["beginner", "intermediate", "advanced"],
        },
        "steps": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 5,
        },
    },
    "required": ["topic", "level", "steps"],
    "additionalProperties": False,
}

response = client.responses.create(
    model=model,
    input=(
        "Turn this request into a compact study plan: learn the OpenAI Responses API "
        "and its text-only capabilities."
    ),
    text={
        "format": {
            "type": "json_schema",
            "name": "study_plan",
            "schema": schema,
            "strict": True,
        }
    },
)

payload = json.loads(response.output_text)
print(json.dumps(payload, indent=2))
