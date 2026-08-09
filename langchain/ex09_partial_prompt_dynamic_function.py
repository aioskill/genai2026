import os
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

OPENAI_MODEL = os.environ["OPENAI_MODEL"]

model = ChatOpenAI(model=OPENAI_MODEL, max_tokens = 1024)


def get_current_date():
    return datetime.now().strftime("%B %d, %Y")

# Define prompt with a dynamic 'date' and a runtime 'user_query'
prompt = ChatPromptTemplate.from_messages([
    ("system", "Today's date is {current_date}."),
    ("human", "{user_query}")
])

# Partially bind the function to 'current_date'
partially_bound_prompt = prompt.partial(current_date=lambda: get_current_date())

# # Build LCEL chain
# chain = partially_bound_prompt | model | StrOutputParser()
#
# # Invoke passing ONLY 'user_query' (current_date is fetched automatically)
# response = chain.invoke({"user_query": "What sports events are happening this month in Bangalore?"})
# print(response)


# Call the model directly to inspect raw metadata
raw_response = model.invoke(partially_bound_prompt.format_messages(
    user_query="What sports events are happening this month in Bangalore?"
))
