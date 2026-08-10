from sentence_transformers import CrossEncoder

"""
pip install sentence-transformers
"""

# Load a pre-trained Cross-Encoder model
# 'ms-marco-MiniLM-L-6-v2' is a fast, accurate model specifically tuned for reranking search results.
# https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2
model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

# Define a user query and candidate documents retrieved from a first-stage search (e.g., Vector DB)
query = "How to fix connection refused error in PostgreSQL?"

documents = [
    "PostgreSQL configuration file is located at /etc/postgresql/main/postgresql.conf.",
    "To resolve connection refused, verify postgresql.service is running and listen_addresses in postgresql.conf is set to '*'.",
    "MySQL uses port 3306 by default for incoming TCP connections.",
    "Python psycopg2 library allows you to connect to PostgreSQL databases using connection strings.",
]

# Form input pairs: [ [Query, Doc1], [Query, Doc2], ... ]
# The Cross-Encoder concatenates each pair: [CLS] Query [SEP] Document
sentence_pairs = [[query, doc] for doc in documents]

# Predict relevance scores for all pairs in a single batch
# Higher score = More relevant
scores = model.predict(sentence_pairs)

# Combine documents with their scores and sort descending
results = list(zip(documents, scores))
results.sort(key=lambda x: x[1], reverse=True)

# Display reranked results
print(f"Query: {query}\n")
print("--- RERANKED RESULTS ---")
for rank, (doc, score) in enumerate(results, 1):
    print(f"Rank {rank} | Score: {score:.4f}")
    print(f"Doc: {doc}\n")