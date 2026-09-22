import os

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
# from langchain_deepseek import ChatDeepSeek
# from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

OPENAI_MODEL = os.environ["OPENAI_MODEL"]

prompt = ChatPromptTemplate.from_template(
    "Explain why openai have removed support "
    "for parameters such as temperature, top_p, top_f, presence_penalty, frequency_penalty "
    "from gpt-6-astra model.")
model = ChatOpenAI(model=OPENAI_MODEL, max_tokens=500)

# Chain piping into StrOutputParser
chain = prompt | model | StrOutputParser()

for chunk in chain.stream({}):
    print(chunk, end="", flush=True)