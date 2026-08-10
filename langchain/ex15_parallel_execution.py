import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

model = ChatOpenAI(model=os.environ["OPENAI_MODEL"])

# Define two separate tasks
summary_chain = ChatPromptTemplate.from_template("Summarize in 10 words: {text}") | model
sentiment_chain = ChatPromptTemplate.from_template("Classify tone: {text}") | model

# Combine into parallel execution
map_chain = RunnableParallel(
    summary=summary_chain,
    sentiment=sentiment_chain
)

result = map_chain.invoke({"text":
"The service was slow, but the waiters were extremely polite and accommodating."})
print(result["summary"].content)
print(result["sentiment"].content)
