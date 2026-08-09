import os
from typing import List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_MODEL = os.environ["OPENAI_MODEL"]

# Define output schema
class Role(BaseModel):
    name: str = Field(description="Name of person")
    role: str = Field(description="Role or title in the company")

class RoleList(BaseModel):
    cxos: List[Role] = Field(description="List of CXO roles", default=[])

model = (ChatOpenAI(model=OPENAI_MODEL)
         .with_structured_output(RoleList, strict = True)
         )
# response is automatically parsed into a Pydantic object
result = model.invoke("Find the CXO's in Palantir")
print(result)