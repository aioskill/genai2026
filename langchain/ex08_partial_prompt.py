from langchain_core.prompts import ChatPromptTemplate

# Define a template requiring 2 variables: 'role' and 'question'
full_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert in {role}."),
    ("human", "{question}")
])

# Partially bind the 'role' variable early
coder_prompt = full_prompt.partial(role="Python Security")
print("Type of code_prompt", type(coder_prompt))
# Later in execution, pass only the remaining 'question' variable
final_messages = coder_prompt.format_messages(question="How do I sanitize SQL inputs?")
# overwrite the value of the template variable set using partial
# final_messages = coder_prompt.format_messages(question="How do I sanitize SQL inputs?", role = "java developer")



print(final_messages[0].content)  # "You are an expert in Python Security."
print(final_messages[1].content)  # "How do I sanitize SQL inputs?"
