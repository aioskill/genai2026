import os

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

load_dotenv()

# Setup Vector Store & Retriever
vectorstore = Chroma.from_texts(
    ["LangChain v1.x standardizes all chains using the Runnable protocol.",
     "LangGraph is recommended for building stateful, multi-actor agents."],
    embedding=OpenAIEmbeddings()
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 1})

# Prompt Template
prompt = ChatPromptTemplate.from_template("""
Answer the question using only the provided context:
Context: {context}
Question: {question}
""")

# LCEL RAG Chain
rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | ChatOpenAI(model=os.environ['OPENAI_MODEL'])
)

print(rag_chain.invoke("What is recommended for building stateful agents?").content)