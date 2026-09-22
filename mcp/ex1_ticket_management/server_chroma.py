import os
import tempfile
import chromadb
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Chroma-Resolutions-Server", port=8002)

# Consolidate directory path under tempfile.gettempdir() / "mcp_ex1" / "chroma"
CHROMA_PATH = os.path.join(tempfile.gettempdir(), "mcp_ex1", "chroma")
os.makedirs(CHROMA_PATH, exist_ok=True)

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="resolved_tickets")

# Seed ChromaDB with past resolution knowledge base
if collection.count() == 0:
    collection.add(
        documents=[
            "ERR_DB_TIMEOUT resolved by increasing max connection_timeout_ms parameter in db_config.json from 1000 to 5000.",
            "ERR_AUTH_FAIL resolved by rotating the client API secret in auth_service.py.",
            "ERR_CACHE_MISS resolved by clearing Redis keys."
        ],
        metadatas=[
            {"error_code": "ERR_DB_TIMEOUT", "resolution_id": "RES-201"},
            {"error_code": "ERR_AUTH_FAIL", "resolution_id": "RES-202"},
            {"error_code": "ERR_CACHE_MISS", "resolution_id": "RES-203"}
        ],
        ids=["res_1", "res_2", "res_3"]
    )


def _resolution_sort_key(item: tuple[str, str, dict]) -> tuple[int, str]:
    _, doc_id, meta = item
    resolution_id = meta.get("resolution_id", "")
    try:
        suffix = int(str(resolution_id).split("-")[-1])
    except (TypeError, ValueError):
        suffix = -1
    return suffix, doc_id


@mcp.resource("chroma://resolutions/latest")
def get_latest_resolutions() -> str:
    """RESOURCE: Passive stream of the 2 most recently indexed resolution documents."""
    # ChromaDB returns ids by default; newer versions reject "ids" in include.
    results = collection.get()
    docs = results.get("documents", [])
    metas = results.get("metadatas", [])
    ids = results.get("ids", [])

    entries = list(zip(docs, ids, metas))
    entries.sort(key=_resolution_sort_key, reverse=True)

    output = []
    for doc, _, meta in entries[:2]:
        output.append(f"[{meta.get('error_code')}]: {doc}")
    return "\n---\n".join(output)


@mcp.tool()
def search_resolutions(description: str) -> list[dict]:
    """TOOL: Semantic vector search for resolutions related to an incident description."""
    results = collection.query(
        query_texts=[description],
        n_results=1,
        include=["documents", "metadatas", "distances"],
    )

    distances = results.get("distances", [[]])
    if not distances or not distances[0]:
        return []

    best_distance = distances[0][0]
    if best_distance is None or best_distance > 1.0:
        return []

    matches = []
    if results["documents"]:
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            matches.append({
                "resolution_fix": doc,
                "error_code": meta.get("error_code")
            })
    return matches


@mcp.tool()
def upsert_resolution(doc_id: str, document: str, error_code: str, resolution_id: str) -> dict:
    """Adds or updates a resolution record in the persistent vector store."""
    collection.upsert(
        documents=[document],
        metadatas=[{"error_code": error_code, "resolution_id": resolution_id}],
        ids=[doc_id],
    )
    return {
        "status": "upserted",
        "doc_id": doc_id,
        "error_code": error_code,
        "resolution_id": resolution_id,
    }

#
# @mcp.tool()
# def upsert_resolution(doc_id: str, document: str, error_code: str, resolution_id: str) -> dict:
#     """Upserts a resolution document into the ChromaDB knowledge base, inserting or replacing by ID."""
#     collection.upsert(
#         ids=[doc_id],
#         documents=[document],
#         metadatas=[{"error_code": error_code, "resolution_id": resolution_id}],
#     )
#     return {"status": "upserted", "doc_id": doc_id, "resolution_id": resolution_id}


@mcp.tool()
def delete_resolution(doc_id: str) -> dict:
    """Deletes a resolution document from the ChromaDB knowledge base by ID."""
    collection.delete(ids=[doc_id])
    return {"status": "deleted", "doc_id": doc_id}


if __name__ == "__main__":
    print(f"ChromaDB initialized at: {CHROMA_PATH}")
    print("Starting Server 2 (ChromaDB Resolutions) on port 8002...")
    mcp.run(transport="sse")
