import pytest

import server_sql


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(server_sql, "DB_PATH", str(tmp_path / "tickets.db"))
    server_sql.init_db()
    return tmp_path / "tickets.db"


class TestServerSQL:
    def test_seed_tickets_present(self, db):
        tickets = server_sql.list_open_tickets()
        assert any(t["ticket_id"] == "TICK-101" for t in tickets)
        assert any(t["ticket_id"] == "TICK-102" for t in tickets)

    def test_list_open_tickets_shape(self, db):
        tickets = server_sql.list_open_tickets()
        assert tickets
        assert set(tickets[0]) == {
            "ticket_id",
            "title",
            "error_code",
        }

    def test_get_ticket_details_found(self, db):
        details = server_sql.get_ticket_details("TICK-101")
        assert details["ticket_id"] == "TICK-101"
        assert details["status"] == "OPEN"
        assert details["error_code"] == "ERR_DB_TIMEOUT"
        assert "affected_file" not in details

    def test_get_ticket_details_not_found(self, db):
        assert server_sql.get_ticket_details("TICK-UNKNOWN") == {
            "error": "Ticket not found"
        }

    def test_add_ticket(self, db):
        ticket = server_sql.Ticket(
            id="TICK-200",
            title="New incident",
            status="OPEN",
            error_code="ERR_NEW",
        )
        assert server_sql.add_ticket(ticket) == {
            "status": "added",
            "ticket_id": "TICK-200",
        }
        details = server_sql.get_ticket_details("TICK-200")
        assert details["title"] == "New incident"

    def test_add_duplicate_ticket(self, db):
        ticket = server_sql.Ticket(
            id="TICK-101",
            title="Duplicate",
            status="OPEN",
            error_code="ERR_X",
        )
        assert server_sql.add_ticket(ticket) == {
            "error": "Ticket TICK-101 already exists"
        }

    def test_update_ticket(self, db):
        ticket = server_sql.Ticket(
            id="TICK-101",
            title="Renamed incident",
            status="IN_PROGRESS",
            error_code="ERR_DB_TIMEOUT",
        )
        result = server_sql.update_ticket(ticket)
        assert result == {"status": "updated", "ticket_id": "TICK-101"}
        details = server_sql.get_ticket_details("TICK-101")
        assert details["title"] == "Renamed incident"
        assert details["status"] == "IN_PROGRESS"

    def test_update_missing_ticket(self, db):
        ticket = server_sql.Ticket(
            id="TICK-NOPE",
            title="x",
            status="OPEN",
            error_code="E",
        )
        assert server_sql.update_ticket(ticket) == {
            "error": "Ticket not found"
        }

    def test_update_ticket_status(self, db):
        assert server_sql.update_ticket_status("TICK-101", "RESOLVED") == {
            "status": "updated",
            "ticket_id": "TICK-101",
            "ticket_status": "RESOLVED",
        }
        details = server_sql.get_ticket_details("TICK-101")
        assert details["status"] == "RESOLVED"

    def test_update_ticket_status_missing(self, db):
        assert server_sql.update_ticket_status("TICK-NOPE", "RESOLVED") == {
            "error": "Ticket not found"
        }

    def test_save_patch_details(self, db):
        result = server_sql.save_patch_details(
            "TICK-101",
            '{"changes":[{"filename":"db_config.json",'
            '"operation":"update",'
            '"content":"{\\n  \\\"connection_timeout_ms\\\": 5000\\n}"}]}',
            "ok",
        )
        assert result["status"] == "saved"
        assert result["ticket_id"] == "TICK-101"
        assert result["changed_files"] == 1

    def test_incident_rca_returns_prompt_messages(self, db):
        server_sql.save_patch_details(
            "TICK-101",
            '{"changes":[{"filename":"db_config.json",'
            '"operation":"update","content":"{}"}]}',
            "ok",
        )
        messages = server_sql.incident_rca("TICK-101")
        assert len(messages) == 2
        assert messages[0].role == "assistant"
        assert messages[1].role == "user"
        assert "TICK-101" in messages[1].content.text

    def test_incident_rca_missing_ticket(self, db):
        messages = server_sql.incident_rca("TICK-NOPE")
        assert "was not found" in messages[1].content.text
        assert "No saved patch details" in messages[1].content.text
