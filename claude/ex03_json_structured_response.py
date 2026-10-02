"""Structured JSON output demonstration using tool use."""

import json
from common import build_client, resolve_model, print_title
from pydantic import BaseModel, Field


class StudyPlan(BaseModel):
    """A structured study plan."""
    topic: str
    level: str = Field(
        description="Difficulty level",
        pattern="^(beginner|intermediate|advanced)$"
    )
    steps: list[str] = Field(min_length=3, max_length=5)


def main() -> None:
    """Generate a structured study plan as JSON."""
    client = build_client()
    model = resolve_model()

    print_title("Structured text output")

    tools = [
        {
            "name": "create_study_plan",
            "description": "Create a structured study plan",
            "input_schema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic to study"
                    },
                    "level": {
                        "type": "string",
                        "enum": ["beginner", "intermediate", "advanced"],
                        "description": "Difficulty level"
                    },
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 5,
                        "description": "Study steps"
                    }
                },
                "required": ["topic", "level", "steps"]
            }
        }
    ]

    response = client.messages.create(
        model=model,
        max_tokens=512,
        tools=tools,
        tool_choice={"type": "tool", "name": "create_study_plan"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Turn this request into a compact study plan: learn the Claude API "
                    "and its text-based capabilities."
                ),
            }
        ],
    )

    # Extract the tool use content
    for block in response.content:
        if block.type == "tool_use":
            payload = block.input
            # Validate with pydantic
            study_plan = StudyPlan(**payload)
            print(json.dumps(study_plan.model_dump(), indent=2))
            return

    print("No tool use block found in response")


if __name__ == "__main__":
    main()
