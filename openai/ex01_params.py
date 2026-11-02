from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()
DEFAULT_MODEL = os.environ["OPENAI_MODEL"]

def print_title(title: str) -> None:
    print(f"\n=== {title} ===")


client = OpenAI()
model = os.environ['OPENAI_MODEL']

print_title("Basic text response")


# Make openai request using response api
response = client.responses.create(
    model=model,
    input=(
        "Explain the difference between temperature and top_p in 4 short sentences. "
        "Keep the answer text-only."
    ),
    text={"verbosity": "medium", "format": {"type": "text"}},
)

print("Response: ", response.output_text)
