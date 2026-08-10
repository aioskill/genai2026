import os
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

from dotenv import load_dotenv

load_dotenv()

# Sample document containing multiple distinct semantic topics
SAMPLE_TEXT = """
Retrieval-Augmented Generation (RAG) is an architectural pattern that improves LLM performance.
Instead of relying only on static training data, RAG fetches relevant context from external databases.
This eliminates hallucinations and provides up-to-date domain knowledge.

Vector databases like ChromaDB, Pinecone, and Qdrant store high-dimensional embeddings.
These databases use approximate nearest neighbor algorithms like HNSW to search millions of vectors in milliseconds.
HNSW builds multi-layered spatial graphs that act like high-speed expressways.

Machine learning models require huge amounts of compute power for training.
Modern GPUs like the NVIDIA H100 provide tensor cores optimized for matrix multiplication.
Data centers must manage massive power and cooling requirements to keep these clusters running.
"""

# =====================================================================
# FIXED-SIZE CHUNKING (CharacterTextSplitter)
# =====================================================================
print("--- 1. FIXED-SIZE CHUNKING ---")

# CharacterTextSplitter splits rigidly by character length or a fixed separator
fixed_splitter = CharacterTextSplitter(
    separator="\n",
    chunk_size=200,      # Maximum character length per chunk
    chunk_overlap=30,    # Number of overlapping characters between chunks
    length_function=len
)

fixed_chunks = fixed_splitter.split_text(SAMPLE_TEXT)

for i, chunk in enumerate(fixed_chunks, 1):
    print(f"[Chunk {i}] ({len(chunk)} chars):\n{chunk.strip()}\n")


# =====================================================================
# RECURSIVE CHARACTER CHUNKING (RecursiveCharacterTextSplitter)
# =====================================================================
print("--- 2. RECURSIVE CHARACTER CHUNKING ---")

# Recursively tries separators: ["\n\n", "\n", " ", ""] to preserve natural paragraphs/sentences
# Step A: Attempt Split on "\n\n" (Paragraph Level)
# The algorithm checks if any paragraph fits inside chunk_size = 200.
# Step B: Recurse to "\n" (Line/Sentence Level)
# so on ...
# To prevent context loss at chunk boundaries, the algorithm steps back 30 characters from the end of Chunk 1.
# It starts Chunk 2 with the tail end of Sentence 2 (or Sentence 2 itself) and attaches Sentence 3 ("This eliminates hallucinations..."

recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=30,
    length_function=len,
    separators=["\n\n", "\n", " ", ""]
)

recursive_chunks = recursive_splitter.split_text(SAMPLE_TEXT)

for i, chunk in enumerate(recursive_chunks, 1):
    print(f"[Chunk {i}] ({len(chunk)} chars):\n{chunk.strip()}\n")


# =====================================================================
# SEMANTIC CHUNKING (SemanticChunker)
# =====================================================================
print("--- 3. SEMANTIC CHUNKING ---")

# Initialize embedding model to compute sentence similarities
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# SemanticChunker calculates distance between consecutive sentence embeddings
# and splits when a semantic topic shift exceeds the breakpoint threshold.
semantic_splitter = SemanticChunker(
    embeddings=embeddings,
    breakpoint_threshold_type="percentile",  # Options: "percentile", "standard_deviation", "interquartile"
    breakpoint_threshold_amount=70           # Split at the 70th percentile of distance shifts
)

semantic_chunks = semantic_splitter.split_text(SAMPLE_TEXT)

for i, chunk in enumerate(semantic_chunks, 1):
    print(f"[Chunk {i}] ({len(chunk)} chars):\n{chunk.strip()}\n")