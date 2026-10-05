import os

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

OPENAI_MODEL = os.environ["OPENAI_MODEL"]

prompt = ChatPromptTemplate.from_template("Tell me a joke about {topic}")
model = ChatOpenAI(model=OPENAI_MODEL)

# Chain piping into StrOutputParser
chain = prompt | model | StrOutputParser()

# response is now a direct python string, NOT an AIMessage
text_response = chain.invoke({"topic": "programming"})
print(type(text_response))
print(text_response)