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
    input="What was a funny news story from today in India?",
)
print("Funny news: ", response.output_text)
follow_up = client.responses.create(
    model=DEFAULT_MODEL,
    previous_response_id=response.id,
    input="why do you find it funny?"
)
print("Why funny: ", follow_up.output_text)