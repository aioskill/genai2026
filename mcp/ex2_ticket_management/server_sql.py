import os
import sqlite3
import tempfile
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP
from mcp.types import PromptMessage, TextContent

mcp = FastMCP("SQL-Support-Tickets-Server", port=8001)

# Consolidate directory path under tempfile.gettempdir() / "mcp_ex1" / "sql"
BASE_DIR = os.path.join(tempfile.gettempdir(), "mcp_ex1", "sql")
os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "tickets.db")


class Ticket(BaseModel):
    """A support ticket record stored in the SQL database."""
    id: str = Field(description="Unique ticket identifier, e.g. TICK-101")
    title: str = Field(description="Short summary of the issue")
    status: str = Field(description="Current lifecycle status, e.g. OPEN")
    error_code: str = Field(description="Known error code associated with the issue")
    affected_file: str = Field(description="Config or code file affected by the issue")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            error_code TEXT,
            affected_file TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patch_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            patch_content TEXT NOT NULL,
            patch_result TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Seed open incidents
    # cursor.execute("""
    #     INSERT OR REPLACE INTO tickets (id, title, status, error_code, affected_file)
    #     VALUES ('TICK-101', 'Database connection timeouts in production', 'OPEN', 'ERR_DB_TIMEOUT', 'db_config.json')
    # """)
    # cursor.execute("""
    #     INSERT OR REPLACE INTO tickets (id, title, status, error_code, affected_file)
    #     VALUES ('TICK-102', 'Legacy printer queue stuck in office', 'OPEN', 'ERR_PRINTER_JAM', 'printer_config.json')
    # """)
    conn.commit()
    conn.close()


init_db()


@mcp.tool()
def list_open_tickets() -> list[dict]:
    """Retrieves all open support tickets from the SQL database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, error_code, affected_file FROM tickets WHERE status = 'OPEN'")
    rows = cursor.fetchall()
    conn.close()

    return [
        {"ticket_id": r[0], "title": r[1], "error_code": r[2], "affected_file": r[3]}
        for r in rows
    ]


@mcp.tool()
def get_ticket_details(ticket_id: str) -> dict:
    """Fetches details for a specific support ticket by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, status, error_code, affected_file FROM tickets WHERE id = ?", (ticket_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Ticket not found"}
    return {"ticket_id": row[0], "title": row[1], "status": row[2], "error_code": row[3], "affected_file": row[4]}


@mcp.tool()
def save_patch_details(ticket_id: str, filename: str, patch_content: str, patch_result: str) -> dict:
    """Persists the applied patch details for incident tracking and audit history."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO patch_history (ticket_id, filename, patch_content, patch_result)
        VALUES (?, ?, ?, ?)
        """,
        (ticket_id, filename, patch_content, patch_result),
    )
    conn.commit()
    patch_id = cursor.lastrowid
    conn.close()

    return {
        "status": "saved",
        "patch_id": patch_id,
        "ticket_id": ticket_id,
        "filename": filename,
    }


@mcp.tool()
def add_ticket(ticket: Ticket) -> dict:
    """Adds a new support ticket record to the SQL database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO tickets (id, title, status, error_code, affected_file) VALUES (?, ?, ?, ?, ?)",
            (ticket.id, ticket.title, ticket.status, ticket.error_code, ticket.affected_file),
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
        "UPDATE tickets SET title = ?, status = ?, error_code = ?, affected_file = ? WHERE id = ?",
        (ticket.title, ticket.status, ticket.error_code, ticket.affected_file, ticket.id),
    )
    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        return {"error": "Ticket not found"}
    return {"status": "updated", "ticket_id": ticket.id}


@mcp.tool()
def update_ticket_status(ticket_id: str, status: str) -> dict:
    """Updates the stored ticket status for escalation and lifecycle tracking."""
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
    return {"status": "updated", "ticket_id": ticket_id, "ticket_status": status}


@mcp.prompt()
def incident_rca(ticket_id: str) -> list[PromptMessage]:
    """MCP Prompt Primitive: Builds an RCA template from live SQL ticket context."""
    ticket = get_ticket_details(ticket_id)
    if ticket.get("error"):
        ticket_context = f"Ticket `{ticket_id}` was not found in the SQL ticket store."
    else:
        ticket_context = (
            f"Ticket ID: {ticket.get('ticket_id', ticket_id)}\n"
            f"Title: {ticket.get('title', 'Unknown')}\n"
            f"Status: {ticket.get('status', 'Unknown')}\n"
            f"Known Error Code: {ticket.get('error_code', 'Unknown')}\n"
            f"Affected File: {ticket.get('affected_file', 'Unknown')}"
        )

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT filename, patch_content, patch_result, created_at
        FROM patch_history
        WHERE ticket_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (ticket_id,),
    )
    patch_row = cursor.fetchone()
    conn.close()

    if patch_row:
        patch_context = (
            f"Filename: {patch_row[0]}\n"
            f"Patch Content:\n{patch_row[1]}\n"
            f"Patch Result: {patch_row[2]}\n"
            f"Saved At: {patch_row[3]}"
        )
    else:
        patch_context = "No saved patch details were found for this ticket."

    system_instruction = (
        "You are an Incident Response SRE. Summarize the incident after live "
        "triage and remediation using the provided ticket telemetry, applied "
        "patch content, and historical resolution context.\n\n"
        "Output Format:\n"
        "1. Executive Summary\n"
        "2. Likely Root Cause\n"
        "3. Recommended Fix (Code/Config Patch)"
    )

    user_context = f"""
    Please generate a closing RCA report for Incident Ticket: **{ticket_id}**

    ### Live Ticket Context:
    {ticket_context}

    ### Applied Patch Details:
    {patch_context}

    ---
    *Instructions:* Use `search_resolutions` from Server 2 to look up matching
    historical fixes and summarize the exact patch content used during remediation.
    """

    return [
        PromptMessage(role="assistant", content=TextContent(type="text", text=system_instruction)),
        PromptMessage(role="user", content=TextContent(type="text", text=user_context)),
    ]


if __name__ == "__main__":
    print(f"SQL Database initialized at: {DB_PATH}")
    print("Starting Server 1 (SQL Tickets) on port 8001...")
    mcp.run(transport="sse")
