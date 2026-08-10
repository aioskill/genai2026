import chromadb
from chromadb.config import Settings
import os
import tempfile

collection_name = "Students"

client = chromadb.PersistentClient(
    path=os.path.join(tempfile.gettempdir(), "chroma_db"),
    settings=Settings(allow_reset=True),
)

# client = chromadb.HttpClient(
#     host="localhost",
#     port=8000,
#     settings=Settings(allow_reset=True),
# )

# https://docs.trychroma.com/docs/collections/configure#python
collection = client.get_or_create_collection(name="Students")

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

# Chroma’s default embedding function uses the Sentence Transformers all-MiniLM-L6-v2 model to create embeddings.
# This embedding model can create sentence and document embeddings that can be used for a wide variety of tasks.
# This embedding function runs locally on your machine, and
# may require you to download the model files (this will happen automatically).

# https://docs.trychroma.com/docs/embeddings/embedding-functions

collection.add(
    documents = [student_info, club_info, university_info],
    metadatas = [{"source": "student info"},
                 {"source": "club info"},
                 {'source':'university info'}],
    ids = ["id1", "id2", "id3"]
)

# To run a similarity search, you can use the query() function and ask questions in natural language.
# It will convert the query into embedding and use similarity algorithms to generate similar results.
# In our case, it is returning two similar results.
results = collection.query(
    query_texts=["What is the student name?"],
    n_results=2
)
print("Query 1: ", results)

# ChromaDB supports metadata filtering to narrow down similarity search results.
# Use the where parameter with filter operators inside query():
results = collection.query(
    query_texts=["What is the student name?"],
    n_results=2,
    where={"source": "student info"}  # only return documents with this metadata
)
print("Query 2: ", results)


# Combine multiple filters with $and / $or
results = collection.query(
    query_texts=["university"],
    n_results=5,
    where={
        "$or": [
            {"source": "student info"},
            {"source": "university info"}
        ]
    }
)
print("Query 3: ", results)

# Included embeddings and distances
results = collection.query(
    query_texts=["What is the student name?"],
    n_results=2,
    include=["embeddings", "documents", "distances"]
)
print("Query 4: ", results)


# Update a document
collection.update(
    ids=["id1"],
    documents=["Kristiane Carina, a 19-year-old computer science sophomore with a 3.7 GPA"],
    metadatas=[{"source": "student info"}],
)
results = collection.query(
    query_texts=["What is the student name?"],
    n_results=2
)
print("Query 4: ", results)



# Update the metadata
# ChromaDB replaces the entire metadata object for that ID.
# It does not merge keys. You must pass all fields you want to keep.
# Data Types: Metadata values must be strings, integers, floats, or booleans.
# Nested dictionaries or lists are not supported.
collection.update(
    ids=["id1"],  # The ID of the document you want to update
    metadatas=[{"source": "student info", "version": 2.0, "tags": ["python", "ai", "database"]}]  # New metadata
)

# Get by id
results = collection.get(ids = ["id1"])
print("Get by ID: ", results)

# Filter by metadata
results = collection.get(where={"source": "student info"})
print("Filter by metadata 1: ", results)

# Filter by tag
results = collection.get(
    where={"tags": {"$contains": "python"}}
)
print("Filter by metadata 2: ", results)

# Get Embeddings
query_results = collection.query(
    query_texts=["What is the student name?"],
    n_results=2,
    include=["embeddings", "documents", "distances"]  # <-- Request embeddings in query output
)
print("View embeddings: ", query_results)

# Fetch all documents and their vector embeddings
all_data = collection.get(
    include=["embeddings", "documents"]
)

all_vectors = all_data["embeddings"]
print("All vectors: ", all_vectors)

# Delete a document
collection.delete(ids = ['id1'])

results = collection.query(
    query_texts=["What is the student name?"],
    n_results=2
)
print("Query 5: ", results)

# Count number of docs in the collection
print("Count of docs: ", collection.count())

# Get all docs
print("All docs: ", collection.get())

# Rename collection
if "chroma_info" in [r.name for r in client.list_collections()]:
    client.delete_collection("chroma_info")
collection.modify(name="chroma_info")

# list all collections
print("List collections: ", client.list_collections())

# Delete a collection
client.delete_collection(name="chroma_info")
print("List collections (after deletion): ", client.list_collections())


# Reset the entire database, does not work HttpClient
client.reset()
print("Collections after reset: ", client.list_collections())