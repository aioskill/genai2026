from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
DEFAULT_MODEL = os.environ["OPENAI_MODEL"]
client = OpenAI()

# List of tools
# https://developers.openai.com/api/docs/guides/tools

response = client.responses.create(
    model=DEFAULT_MODEL,
    tools=[{"type": "web_search"}],
    input="What was a positive news story from today?",
)

print(response.output_text)