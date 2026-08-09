import os

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

OPENAI_MODEL = os.environ["OPENAI_MODEL"]

model = ChatOpenAI(model=OPENAI_MODEL, max_tokens = 500)

# Define the message history using langchain_core
prompt1 = ChatPromptTemplate.from_messages([
    SystemMessage(content="Answer questions in the style of a politician."),
    HumanMessage(content="Do you support increase of government spending on public health?") # static message
])

prompt2 = ChatPromptTemplate.from_messages([
    SystemMessage(content="Answer questions in the style of a politician."),
    HumanMessagePromptTemplate.from_template("Do you support increase of government spending on {topic}?") # templated messages
])

prompt3 = ChatPromptTemplate.from_messages([
    ("system", "Answer questions in the style of a politician."),
    ("human", "Do you support increase of government spending on {topic}?")
])

chain = prompt2 | model | StrOutputParser()
response = chain.invoke({"topic": "AI data centers"})
# response = chain.invoke({"topic": "public schools"})
print(response)
