import click
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
DEFAULT_MODEL = os.environ["OPENAI_MODEL"]

SYSTEM_PROMPT = "You are a smart and helpful assistant."


def build_client() -> OpenAI:
    return OpenAI()

def make_request(client, conversation_id, message:str, model = DEFAULT_MODEL):
    return client.responses.create(
        model=model,
        conversation={"id": conversation_id},
        instructions=SYSTEM_PROMPT,
        input=message,
        temperature=1.0,
        max_output_tokens=256,
        store=False,
        # top_p=0.9,
        # frequency_penalty=0.0,
        # presence_penalty=0.0
    )

"""
Find the next output in the sequence. 
Below are a few examples:
====
Input: 1 Output: X
Input: 2 Output: Y
Input: 3 Output: Z
====

Input: 4 Output: 

"""

def chat_with_felix():
    """Chat with Felix, the chatbot."""
    client = build_client()
    # Initialize conversation with few-shot training items
    conversation = client.conversations.create(
        metadata={"bot": "felix-chatbot"},
        items=[
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "X"},
            {"role": "user", "content": "2"},
            {"role": "assistant", "content": "Y"},
        ]
    )
    for message in ("3", "4", "alpha"):
        response = make_request(client, conversation.id, message)
        output_text = getattr(response, "output_text", None) or "No response generated."
        print(f"User: {message}, Felix: {output_text}")


if __name__ == '__main__':
    chat_with_felix()