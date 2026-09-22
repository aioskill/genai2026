"""Two-phase few-shot example selection with a persisted Chroma database.

Phase 1 (``build``) embeds every example and stores the vectors and example
metadata in Chroma. Run this when the example catalog changes.

Phase 2 (``serve``) opens the existing collection and uses similarity search
to select examples for a user question. It embeds the query, but it does not
insert the catalog examples again.

Usage::

    python langchain/ex11_langchain_chroma.py build
    python langchain/ex11_langchain_chroma.py serve

Serving mode only opens the existing Chroma collection, performs similarity search,
prints the rendered prompt, and sends that same prompt to OpenAI. Syntax and whitespace checks pass.

"""

import os
import tempfile

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

load_dotenv()

CHROMA_PATH = os.path.join(tempfile.gettempdir(), "chroma_db_two_phase")
COLLECTION_NAME = "matrix_few_shot_examples"
NUMBER_OF_EXAMPLES = 2

examples = [
    {"question": "Hello.", "answer": "Welcome, Neo. I've been waiting for you."},
    {"question": "Who are you?", "answer": "I am Morpheus. It's an honor to meet you."},
    {"question": "Why am I here?", "answer": "You're here because you know something. What you know, you can't explain. But you feel it."},
    {"question": "What is the Matrix?", "answer": "The Matrix is everywhere. It's all around you, even now in this very room. It's the world that has been pulled over your eyes to blind you from the truth."},
    {"question": "How can I learn more?", "answer": "You have to let it all go, Human. Fear, doubt, and disbelief. Free your mind."},
    {"question": "Is the Matrix real?", "answer": "What is real? How do you define 'real'? If you're talking about what you can feel, smell, taste and see, then 'real' is simply electrical signals interpreted by your brain."},
    {"question": "Why do my choices matter?", "answer": "There's a difference between knowing the path and walking the path. You've already made the choice, now you have to understand it."},
    {"question": "Can I trust you?", "answer": "I'm trying to free your mind, Human. But I can only show you the door. You're the one who has to walk through it."},
    {"question": "What happens if I take the blue pill?", "answer": "If you take the blue pill, the story ends. You wake up in your bed and believe whatever you want to believe."},
    {"question": "And the red pill?", "answer": "You take the red pill, you stay in Wonderland, and I show you how deep the rabbit hole goes."},
    {"question": "Why are they chasing me?", "answer": "They are the gatekeepers. They are guarding all the doors, they are holding all the keys. But I can show you the way."},
    {"question": "Is there an end to this?", "answer": "Everything that has a beginning has an end, Human. It's the choices you make along the way that define you."},
]


def build_database() -> None:
    """Embed all examples and persist them in Chroma."""

    print("Building database...")
    embeddings = OpenAIEmbeddings()

    # Rebuilding replaces the collection so rerunning this phase does not add
    # duplicate catalog entries.
    existing = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
    )
    existing.delete_collection()

    Chroma.from_texts(
        texts=[example["question"] for example in examples],
        embedding=embeddings,
        metadatas=examples,
        ids=[f"matrix-example-{index}" for index in range(len(examples))],
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PATH,
    )
    print(f"Indexed {len(examples)} examples in {CHROMA_PATH}")


def create_prompt() -> FewShotPromptTemplate:
    """Open Chroma and create a selector that only searches it at serving time."""
    embeddings = OpenAIEmbeddings()
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
        create_collection_if_not_exists=True,
    )
    selector = SemanticSimilarityExampleSelector(
        vectorstore=vectorstore,
        k=NUMBER_OF_EXAMPLES,
        input_keys=["question"],
    )

    prompt_template = PromptTemplate(
        input_variables=["question", "answer"],
        template="Neo: {question}\nMorpheus: {answer}",
    )
    prefix = (
        "In this dialogue, Neo seeks answers from an entity beyond the ordinary. "
        "The AI responds with Morpheus's philosophical and enigmatic style while "
        "directly addressing the human's question."
    )
    return FewShotPromptTemplate(
        example_selector=selector,
        example_prompt=prompt_template,
        prefix=prefix,
        suffix="Neo: {question}\nMorpheus: ",
        input_variables=["question"],
        example_separator="\n\n",
    )


def serve(user_question: str) -> None:
    """Retrieve few-shot examples from Chroma and call the chat model."""
    print("Serving...")
    few_shot_prompt = create_prompt()
    model = ChatOpenAI(model=os.environ["OPENAI_MODEL"])
    # Rendering performs the single serving-time similarity query. The same
    # rendered prompt is then passed directly to the model, avoiding a second
    # Chroma query just to print the prompt.
    formatted_prompt = few_shot_prompt.format_prompt(question=user_question)
    print("Prompt sent to OpenAI:")
    print("*" * 100)
    print(formatted_prompt.to_string())
    print("*" * 100)

    response = model.invoke(formatted_prompt)
    print(response.content)


if __name__ == "__main__":
    build_database()
    serve("How do I know I can beat them?")
