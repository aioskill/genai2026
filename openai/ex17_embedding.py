from openai import OpenAI
from dotenv import load_dotenv
import numpy as np
load_dotenv()

# Initialize the OpenAI client
client = OpenAI()

# ------------------------------------------------------------------
# Truncating 'text-embedding-3-small' from 1,536 down to 512 dims
# ------------------------------------------------------------------
response_small = client.embeddings.create(
    model="text-embedding-3-small",
    input="Vector databases enable fast semantic search.",
    dimensions=512  # <-- Custom reduced dimension
)

vector_small = response_small.data[0].embedding

print(f"Model: text-embedding-3-small")
print(f"Requested Dimensions: 512")
print(f"Actual Vector Length: {len(vector_small)}")
print(f"Sample Vector Output: {vector_small[:3]}...\n")


# ------------------------------------------------------------------
# Truncating 'text-embedding-3-large' from 3,072 down to 1,024 dims
# ------------------------------------------------------------------
response_large = client.embeddings.create(
    model="text-embedding-3-large",
    input="Vector databases enable fast semantic search.",
    dimensions=1024  # <-- Custom reduced dimension
)

vector_large = response_large.data[0].embedding

print(f"Model: text-embedding-3-large")
print(f"Requested Dimensions: 1024")
print(f"Actual Vector Length: {len(vector_large)}")
print(f"Sample Vector Output: {vector_large[:3]}...")

norm = np.linalg.norm(vector_large)
print(f"Norm : {norm}")