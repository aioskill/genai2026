import uuid

import chromadb
import pytest

import server_chroma

SEED_DOCUMENTS = [
    "ERR_DB_TIMEOUT resolved by increasing max connection_timeout_ms parameter in db_config.json from 1000 to 5000.",
    "ERR_AUTH_FAIL resolved by rotating the client API secret in auth_service.py.",
    "ERR_CACHE_MISS resolved by clearing Redis keys.",
]
SEED_METADATAS = [
    {"error_code": "ERR_DB_TIMEOUT", "resolution_id": "RES-201"},
    {"error_code": "ERR_AUTH_FAIL", "resolution_id": "RES-202"},
    {"error_code": "ERR_CACHE_MISS", "resolution_id": "RES-203"},
]
SEED_IDS = ["res_1", "res_2", "res_3"]


@pytest.fixture
def collection(monkeypatch):
    client = chromadb.EphemeralClient()
    col = client.get_or_create_collection(name=f"test_resolved_tickets_{uuid.uuid4().hex}")
    col.add(
        documents=SEED_DOCUMENTS,
        metadatas=SEED_METADATAS,
        ids=SEED_IDS,
    )
    monkeypatch.setattr(server_chroma, "collection", col)
    return col


class TestServerChroma:
    def test_get_latest_resolutions_returns_two(self, collection):
        output = server_chroma.get_latest_resolutions()
        assert "ERR_CACHE_MISS" in output
        assert "ERR_AUTH_FAIL" in output
        assert "ERR_DB_TIMEOUT" not in output

    def test_search_resolutions_match(self, collection):
        matches = server_chroma.search_resolutions(
            "database connection keeps timing out"
        )
        assert matches
        assert matches[0]["error_code"] == "ERR_DB_TIMEOUT"
        assert "ERR_DB_TIMEOUT" in matches[0]["resolution_fix"]

    def test_search_resolutions_no_match(self, collection):
        assert server_chroma.search_resolutions("banana smoothie recipe") == []

    def test_search_resolutions_empty_collection(self, monkeypatch):
        client = chromadb.EphemeralClient()
        empty = client.get_or_create_collection(name=f"test_empty_resolutions_{uuid.uuid4().hex}")
        monkeypatch.setattr(server_chroma, "collection", empty)
        assert server_chroma.search_resolutions("anything") == []

    def test_upsert_resolution_inserts(self, collection):
        result = server_chroma.upsert_resolution(
            doc_id="res_4",
            document="ERR_RATE_LIMIT resolved by enabling token bucket throttling.",
            error_code="ERR_RATE_LIMIT",
            resolution_id="RES-204",
        )
        assert result["status"] == "upserted"
        assert result["doc_id"] == "res_4"
        assert collection.count() == 4

    def test_upsert_resolution_replaces_existing(self, collection):
        server_chroma.upsert_resolution(
            doc_id="res_1",
            document="ERR_DB_TIMEOUT resolved by a brand new fix.",
            error_code="ERR_DB_TIMEOUT",
            resolution_id="RES-901",
        )
        matches = server_chroma.search_resolutions("database timeout new fix")
        assert matches
        assert "brand new fix" in matches[0]["resolution_fix"]

    def test_delete_resolution(self, collection):
        result = server_chroma.delete_resolution(doc_id="res_1")
        assert result == {"status": "deleted", "doc_id": "res_1"}
        assert collection.count() == 2

    def test_upsert_resolution_exposes_mcp_tool(self, collection):
        tools = [t.name for t in server_chroma.mcp._tool_manager.list_tools()]
        assert "upsert_resolution" in tools
        assert "search_resolutions" in tools
        assert "delete_resolution" in tools

    def test_resources_exposed(self, collection):
        resources = server_chroma.mcp._resource_manager.list_resources()
        assert any(r.name == "get_latest_resolutions" for r in resources)
        assert any(str(r.uri) == "chroma://resolutions/latest" for r in resources)
