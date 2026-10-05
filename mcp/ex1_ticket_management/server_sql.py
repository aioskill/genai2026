import json
import os
import sqlite3
import tempfile
from typing import Literal
from mcp.server.fastmcp import FastMCP
from mcp.types import PromptMessage, TextContent
from models import PatchProposal, Ticket

mcp = FastMCP("SQL-Support-Tickets-Server", port=8001)

# Consolidate directory path under tempfile.gettempdir() / "mcp_ex1" / "sql"
BASE_DIR = os.path.join(tempfile.gettempdir(), "mcp_ex1", "sql")
os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "tickets.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            applications TEXT,
            status TEXT,
            error_code TEXT,
            patch_details TEXT,
            patch_result TEXT,
            patch_status TEXT,
            patch_error TEXT,
            rca_report TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patch_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT NOT NULL,
            application_name TEXT NOT NULL DEFAULT '',
            host_name TEXT NOT NULL DEFAULT 'localhost',
            filename TEXT NOT NULL,
            patch_content TEXT NOT NULL,
            patch_result TEXT NOT NULL,
            operation TEXT NOT NULL DEFAULT 'update',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_ticket_columns(cursor)
    conn.commit()
    conn.close()


def _ensure_ticket_columns(cursor: sqlite3.Cursor) -> None:
    existing_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(tickets)")
    }
    new_columns = {
        "description": "TEXT",
        "applications": "TEXT",
        "patch_details": "TEXT",
        "patch_result": "TEXT",
        "patch_status": "TEXT",
        "patch_error": "TEXT",
        "rca_report": "TEXT",
    }
    for column, data_type in new_columns.items():
        if column not in existing_columns:
            cursor.execute(
                f"ALTER TABLE tickets ADD COLUMN {column} {data_type}"
            )
    history_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(patch_history)")
    }
    if "operation" not in history_columns:
        cursor.execute(
            "ALTER TABLE patch_history ADD COLUMN operation TEXT "
            "DEFAULT 'update'"
        )
    if "application_name" not in history_columns:
        cursor.execute(
            "ALTER TABLE patch_history ADD COLUMN application_name TEXT "
            "NOT NULL DEFAULT ''"
        )
    if "host_name" not in history_columns:
        cursor.execute(
            "ALTER TABLE patch_history ADD COLUMN host_name TEXT "
            "NOT NULL DEFAULT 'localhost'"
        )


init_db()


@mcp.tool()
def list_open_tickets() -> list[dict]:
    """Retrieves open tickets and tickets waiting for an RCA retry."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, description, error_code, applications
        FROM tickets
        WHERE status IN ('OPEN', 'PATCHED_PENDING_RCA')
        """
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "ticket_id": row[0],
            "title": row[1],
            "description": row[2],
            "error_code": row[3],
            "applications": json.loads(row[4] or "[]"),
        }
        for row in rows
    ]


@mcp.tool()
def get_ticket_details(ticket_id: str) -> dict:
    """Fetches details for a specific support ticket by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, description, applications, status, error_code,
               patch_details, patch_result, patch_status, patch_error,
               rca_report
        FROM tickets WHERE id = ?
        """,
        (ticket_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Ticket not found"}
    return {
        "ticket_id": row[0],
        "title": row[1],
        "description": row[2],
        "applications": json.loads(row[3] or "[]"),
        "status": row[4],
        "error_code": row[5],
        "patch_details": row[6],
        "patch_result": row[7],
        "patch_status": row[8],
        "patch_error": row[9],
        "rca_report": row[10],
    }


@mcp.tool()
def save_patch_details(
    ticket_id: str,
    patch_details: str,
    patch_result: str,
) -> dict:
    """Saves all applied file changes on the ticket and in patch history."""
    try:
        proposal = PatchProposal.model_validate_json(patch_details)
    except ValueError as exc:
        return {"error": f"Invalid patch details: {exc}"}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE tickets
        SET patch_details = ?, patch_result = ?
        WHERE id = ?
        """,
        (patch_details, patch_result, ticket_id),
    )
    if cursor.rowcount == 0:
        conn.close()
        return {"error": "Ticket not found"}

    for change in proposal.changes:
        cursor.execute(
            """
            INSERT INTO patch_history (
                ticket_id, application_name, host_name, filename,
                patch_content, patch_result, operation
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                change.application_name,
                change.host_name,
                change.filename,
                change.content or "",
                patch_result,
                change.operation,
            ),
        )
    conn.commit()
    conn.close()

    return {
        "status": "saved",
        "ticket_id": ticket_id,
        "changed_files": len(proposal.changes),
    }


@mcp.tool()
def save_incident_rca(ticket_id: str, rca_report: str) -> dict:
    """Saves a generated RCA report directly on its ticket."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tickets SET rca_report = ? WHERE id = ?",
        (rca_report, ticket_id),
    )
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    if updated == 0:
        return {"error": "Ticket not found"}
    return {"status": "saved", "ticket_id": ticket_id}


@mcp.tool()
def save_patch_status(
    ticket_id: str,
    patch_status: Literal["SUCCESS", "FAILURE"],
    error_message: str | None = None,
) -> dict:
    """Saves the patch outcome and any error message on its ticket."""
    normalized_status = patch_status.upper()
    if normalized_status not in {"SUCCESS", "FAILURE"}:
        return {"error": "patch_status must be SUCCESS or FAILURE"}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE tickets
        SET patch_status = ?, patch_error = ?
        WHERE id = ?
        """,
        (normalized_status, error_message, ticket_id),
    )
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    if updated == 0:
        return {"error": "Ticket not found"}
    return {
        "status": "saved",
        "ticket_id": ticket_id,
        "patch_status": normalized_status,
    }


@mcp.tool()
def get_patch_history() -> list[dict]:
    """Returns recent applied file changes for LLM remediation context."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT ticket_id, application_name, host_name, filename, operation,
               patch_content, patch_result, created_at
        FROM patch_history
        ORDER BY created_at DESC, id DESC
        LIMIT 50
        """,
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "ticket_id": row[0],
            "application_name": row[1],
            "host_name": row[2],
            "filename": row[3],
            "operation": row[4],
            "patch_content": row[5],
            "patch_result": row[6],
            "created_at": row[7],
        }
        for row in rows
    ]


@mcp.tool()
def clear_all_records() -> dict:
    """Deletes all ticket and patch-history records before demo seeding."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM patch_history")
    deleted_patch_history = cursor.rowcount
    cursor.execute("DELETE FROM tickets")
    deleted_tickets = cursor.rowcount
    conn.commit()
    conn.close()
    return {
        "status": "cleared",
        "deleted_tickets": deleted_tickets,
        "deleted_patch_history": deleted_patch_history,
    }


@mcp.tool()
def add_ticket(ticket: Ticket) -> dict:
    """Adds a new support ticket record to the SQL database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO tickets (
                id, title, description, applications, status, error_code
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ticket.id,
                ticket.title,
                ticket.description,
                json.dumps([
                    application.model_dump()
                    for application in ticket.applications
                ]),
                ticket.status,
                ticket.error_code,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return {"error": f"Ticket {ticket.id} already exists"}
    conn.close()
    return {"status": "added", "ticket_id": ticket.id}


@mcp.tool()
def update_ticket(ticket: Ticket) -> dict:
    """Updates an existing support ticket record in the SQL database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE tickets
        SET title = ?, description = ?, applications = ?, status = ?,
            error_code = ?
        WHERE id = ?
        """,
        (
            ticket.title,
            ticket.description,
            json.dumps([
                application.model_dump()
                for application in ticket.applications
            ]),
            ticket.status,
            ticket.error_code,
            ticket.id,
        ),
    )
    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        return {"error": "Ticket not found"}
    return {"status": "updated", "ticket_id": ticket.id}


@mcp.tool()
def update_ticket_status(ticket_id: str, status: str) -> dict:
    """Updates ticket status for escalation and lifecycle tracking."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tickets SET status = ? WHERE id = ?",
        (status, ticket_id),
    )
    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        return {"error": "Ticket not found"}
    return {
        "status": "updated",
        "ticket_id": ticket_id,
        "ticket_status": status,
    }


@mcp.prompt()
def incident_rca(ticket_id: str) -> list[PromptMessage]:
    """Builds an RCA prompt from live SQL ticket context."""
    ticket = get_ticket_details(ticket_id)
    if ticket.get("error"):
        ticket_context = (
            f"Ticket `{ticket_id}` was not found in the SQL ticket store."
        )
    else:
        ticket_context = (
            f"Ticket ID: {ticket.get('ticket_id', ticket_id)}\n"
            f"Title: {ticket.get('title', 'Unknown')}\n"
            f"Description: {ticket.get('description') or 'Not provided'}\n"
            f"Applications: {ticket.get('applications') or []}\n"
            f"Status: {ticket.get('status', 'Unknown')}\n"
            f"Known Error Code: {ticket.get('error_code', 'Unknown')}\n"
            f"Patch Status: {ticket.get('patch_status', 'Unknown')}\n"
            f"Patch Error: {ticket.get('patch_error', 'None')}"
        )

    patch_context = ticket.get("patch_details") or (
        "No saved patch details were found for this ticket."
    )

    system_instruction = (
        "You are an Incident Response SRE writing a factual remediation "
        "record from the provided ticket telemetry, applied patch content, "
        "and historical resolution context. Do not claim the incident is "
        "resolved or the behavior is verified without test or runtime "
        "evidence. Mark inferred causes as likely. Never invent dates or "
        "include placeholders.\n\n"
        "Output Format:\n"
        "1. Executive Summary\n"
        "2. Likely Root Cause\n"
        "3. Recommended Fix (Code/Config Patch)"
    )

    user_context = f"""
    Please generate an incident RCA for Ticket: **{ticket_id}**

    ### Live Ticket Context:
    {ticket_context}

    ### Applied Patch Details:
    {patch_context}

    ---
    *Instructions:* Use the supplied historical resolutions and summarize the
    exact patch content used during remediation.
    """

    return [
        PromptMessage(
            role="assistant",
            content=TextContent(type="text", text=system_instruction),
        ),
        PromptMessage(
            role="user",
            content=TextContent(type="text", text=user_context),
        ),
    ]


if __name__ == "__main__":
    print(f"SQL Database initialized at: {DB_PATH}")
    print("Starting Server 1 (SQL Tickets) on port 8001...")
    mcp.run(transport="sse")
