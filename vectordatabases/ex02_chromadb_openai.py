import chromadb
import os
from dotenv import load_dotenv
from chromadb.utils import embedding_functions

load_dotenv()

OPENAI_TOKEN = os.environ["OPENAI_API_KEY"]

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_TOKEN,
    model_name="text-embedding-3-small"
)

collection_name = "Students"

client = chromadb.PersistentClient(path=os.path.join("tmp", "chroma_db"))

# https://docs.trychroma.com/docs/collections/configure#python
collection = client.get_or_create_collection(name="Students2", embedding_function=openai_ef)

student_info = """
Alexandra Thompson, a 19-year-old computer science sophomore with a 3.7 GPA,
is a member of the programming and chess clubs who enjoys pizza, swimming, and hiking
in her free time in hopes of working at a tech company after graduating from the University of Washington.
"""

club_info = """
The university chess club provides an outlet for students to come together and enjoy playing
the classic strategy game of chess. Members of all skill levels are welcome, from beginners learning
the rules to experienced tournament players. The club typically meets a few times per week to play casual games,
participate in tournaments, analyze famous chess matches, and improve members' skills.
"""

university_info = """
The University of Washington, founded in 1861 in Seattle, is a public research university
with over 45,000 students across three campuses in Seattle, Tacoma, and Bothell.
As the flagship institution of the six public universities in Washington state,
UW encompasses over 500 buildings and 20 million square feet of space,
including one of the largest library systems in the world.
"""

students_embeddings = openai_ef([student_info, club_info, university_info])
print(students_embeddings)

collection.add(
    documents = [student_info, club_info, university_info],
    metadatas = [{"source": "student info"},{"source": "club info"},{'source':'university info'}],
    ids = ["id1", "id2", "id3"]
)

# To run a similarity search, you can use the query() function and ask questions in natural language.
# It will convert the query into embedding and use similarity algorithms to generate similar results.
# In our case, it is returning two similar results.
results = collection.query(
    query_texts=["What is the student name?"],
    n_results=2
)

print(results)