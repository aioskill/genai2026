import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

"""
Best practice:  
- Prefer Pydantic (with_structured_output) for JSON: 
  It guarantees strict schema validation and eliminates JSON parsing errors.
- Convert validated data to YAML: Rather than asking the LLM to write 
  raw YAML (which can suffer from indentation bugs), generate validated 
  JSON/Pydantic data first, then dump it using yaml.dump(data).
- Always mention 'JSON' in System Prompts: 
  When using response_format={"type": "json_object"}, 
  OpenAI APIs will raise an error if the word "JSON" does not 
  appear somewhere in your prompt/messages.
Note: use instructor package for json response parsing if you are not using langchain
"""


load_dotenv()

OPENAI_MODEL = os.environ["OPENAI_MODEL"]
model = ChatOpenAI(model=OPENAI_MODEL)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert developer. Output ONLY valid YAML code. Do not wrap in markdown fences or extra text."),
    ("user", "Create a Kubernetes deployment configuration for a Nginx web server.")
])

chain = prompt | model | StrOutputParser()

response = chain.invoke({})
print(response)