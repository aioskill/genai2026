import os

# from langchain_openai import ChatOpenAI
# from langchain_deepseek import ChatDeepSeek
# from langchain_ollama import ChatOllama
# from langchain_anthropic import ChatAnthropic
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

model_name = os.environ["OPENAI_MODEL"]
# model_name = os.environ["ANTHROPIC_MODEL"]


prompt = ChatPromptTemplate.from_template(
    "Explain: {topic}. Show raw texts in bullets. Keep output text short")
#model = ChatOpenAI(model=model_name, max_tokens = 1024)
#model = ChatAnthropic(model=model_name, max_tokens = 1024)

model = init_chat_model(f"openai:{model_name}", max_tokens = 1024)

topic = "quantum computing"

resolved_prompt = prompt.format_messages(topic = topic)
print("Resolved prompt:", resolved_prompt[0].content)

# This expression is called LCEL (LangChain Expression Language)
# This a static chain defined by the developer
# If you need a dynamic execution chain, look into langgraph
chain = prompt | model
response = chain.invoke({"topic": topic})

# Plain Text Output
print("======= LLM response ======\n", response.content)
print("===========================\n")


# Token Usage Metadata
if response.usage_metadata:
    print("Input Tokens:", response.usage_metadata["input_tokens"])
    print("Output Tokens:", response.usage_metadata["output_tokens"])
print("Finish Reason:", response.response_metadata.get("finish_reason"))
