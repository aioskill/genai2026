import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# Define target schema in pydantic class
class MovieReview(BaseModel):
    sentiment: str = Field(description="Positive, Negative, or Neutral")
    summary: str = Field(description="One sentence summary of the review")

parser = JsonOutputParser(pydantic_object=MovieReview)

# Define Prompt Template
prompt = ChatPromptTemplate.from_messages([
    ("system", "Analyze the movie review. {format_instructions}"),
    ("human", "{review}")
]).partial(format_instructions=parser.get_format_instructions())

print("format_instructions: ", parser.get_format_instructions())

# Instantiate Model
model = ChatOpenAI(model=os.environ["OPENAI_MODEL"])

# Chain Execution via LCEL
chain = prompt | model | parser

print("=" * 100)

response = chain.invoke({"review": "The visual effects were stunning, but the plot fell completely flat."})
print("Review analysis (dict): ",response)
mr = MovieReview.model_validate(response)# Outputs a dictionary matching MovieReview schema
print("Movie review instance: ", mr)
