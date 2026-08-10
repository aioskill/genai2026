import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
DEFAULT_MODEL = os.environ["OPENAI_MODEL"]


def build_client() -> OpenAI:
    return OpenAI()


def chat_with_felix():
    """Chat with Felix, the chatbot."""
    client = build_client()
    user_request = """
        When James was 2 years old, his sister was 4 years old. James is now 
        30 years old. How old is his sister?
    """
    response = client.responses.create(
        model=DEFAULT_MODEL,
        input=user_request,
        instructions = ("Think step by step. In the output include the reasoning in bullets. "
                       "Provide the output as raw, unformatted text. ")
    )
    output_text = getattr(response, "output_text", None) or "No response generated."
    print(f"AI: \n{output_text}")


if __name__ == '__main__':
    chat_with_felix()