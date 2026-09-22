from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

"""
All models do not support all model parameters
"""

# OpenAI
llm_openai = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
    top_p=0.9,
    frequency_penalty=0.5,
    presence_penalty=0.5,
    max_tokens=500,
)

# llm = ChatAnthropic()

# # DeepSeek
# llm_deepseek = ChatDeepSeek(
#     model="deepseek-chat",
#     temperature=0.3,
#     top_p=0.85,
#     max_tokens=1000,
# )
#
# # Ollama
# llm_ollama = ChatOllama(
#     model="llama3",
#     temperature=0.2,
#     top_p=0.9,
# )

# Usage remains identical for all models
response = llm_openai.invoke("Give me 3 creative naming ideas for a coffee shop.")
print(response.content)