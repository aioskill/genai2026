import os
import sys
from dotenv import load_dotenv
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain_openai import ChatOpenAI

load_dotenv()

# System message template
template = """You are a helpful assistant that translates from {from_lang} to {to_lang}.
Your output should be in JSON format.

Examples:
user: translate(Hello, en, es)
ai:
{{
    "sentence": "Hello",
    "translation": "Hola",
    "from_lang": "en",
    "to_lang": "es"
}}

user: translate(Would you like to play a game?, en, es)
ai:
{{
    "sentence": "Would you like to play a game?",
    "translation": "¿Te gustaría jugar un juego?",
    "from_lang": "en",
    "to_lang": "es"
}}

A user will pass in the sentence to translate, and your output should ONLY return the translation in the JSON format above, and nothing more."""

# Message prompt templates
system_message_prompt = SystemMessagePromptTemplate.from_template(template)
human_template = "translate({sentence}, {from_lang}, {to_lang})"
human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)

# Compose ChatPromptTemplate
chat_prompt = ChatPromptTemplate.from_messages([
    system_message_prompt,
    human_message_prompt,
])

# Initialize Model with JSON enforcement enabled
model = ChatOpenAI(
    model=os.environ["OPENAI_MODEL"],
    model_kwargs={"response_format": {"type": "json_object"}}
)

# Construct LCEL Chain
chain = chat_prompt | model


# Helper function to read and parse the CLI input
def read_parse_user_input(raw_input: str):
    raw_input = raw_input.replace("translate(", "").replace(")", "")
    parts = [item.strip() for item in raw_input.split(",")]
    return parts[0], parts[1], parts[2]


# Main execution flow
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py \"translate(Hello, en, es)\"")
        sys.exit(1)

    user_input = sys.argv[1]
    sentence, from_lang, to_lang = read_parse_user_input(user_input)

    # Invoke chain passing arguments in a dictionary
    output = chain.invoke({
        "sentence": sentence,
        "from_lang": from_lang,
        "to_lang": to_lang
    })
    print(output.content)