from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

"""
All models do not support all model parameters
"""

# OpenAI
model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=1.2,
    top_p=0.95,
    frequency_penalty=0.5,
    presence_penalty=0.5,
    max_tokens=500,
)

# model = ChatAnthropic()

# # DeepSeek
# model = ChatDeepSeek(
#     model="deepseek-chat",
#     temperature=0.3,
#     top_p=0.85,
#     max_tokens=1000,
# )
#
# # Ollama
# model = ChatOllama(
#     model="llama3",
#     temperature=0.2,
#     top_p=0.9,
# )

# Usage remains identical for all models
response = model.invoke("Give me 10 creative naming ideas for a coffee shop. "
                        "Produce text in plan text. Do not use any markdown/html fences.")
print(response.content)