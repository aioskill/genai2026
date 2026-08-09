from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
OPENAI_MODEL = os.environ["OPENAI_MODEL"]
client = OpenAI()

response = client.responses.create(
    model=OPENAI_MODEL,
    input="List 3 primary colors with their hex codes. Write the response in valid JSON format.",
    text={
        "format": {
            "type": "json_object"
        }
    }
)

# Read the generated response directly using output_text
print(response.output_text)