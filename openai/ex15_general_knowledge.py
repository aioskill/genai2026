import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()
MODEL_NAME = os.getenv("OPENAI_MODEL")


def answer_with_generated_knowledge(question: str) -> str:
    # Generate Knowledge
    knowledge_response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": f"Generate 3 concise background facts or principles necessary to answer this question: '{question}'"
            }
        ],
        # temperature=0.3,
        #reasoning_effort="none"
    )
    generated_knowledge = knowledge_response.choices[0].message.content
    print(f"="*100)
    print(f"Generated knowledge: {generated_knowledge}")
    print(f"=" * 100)
    # Integrate Knowledge for Final Answer
    final_response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "Answer the question accurately using the provided background knowledge."
            },
            {
                "role": "user",
                "content": f"Background Knowledge:\n{generated_knowledge}\n\nQuestion: {question}"
            }
        ],
        # temperature=0.0
    )
    return final_response.choices[0].message.content


# Example Query
result = answer_with_generated_knowledge("Is it safe to place a sealed glass jar full of water in the freezer?")
print(result)