
This lab repository demonstrates the Model Context Protocol (MCP) using a decoupled, multi-server microservice architecture. It provides a complete, hands-on example of how an LLM or Orchestrator Client interacts across multiple protocol primitives (Tools, Resources, and Prompts) with Server-Sent Events (SSE) and Human-in-the-Loop (HITL) security gates.


## System Architecture

Instead of a monolithic server, this lab separates concerns into three distinct MCP microservices running over independent SSE ports:

| 🗄️ Server 1: SQL Tickets | 🔍 Server 2: ChromaDB Resolutions | 🛠️ Server 3: Patch Executor |
| :--- | :--- | :--- |
| **Port:** `8001` | **Port:** `8002` | **Port:** `8003` |
| **Domain:** Live Support & Ticket Lifecycle | **Domain:** Vector Search & Knowledge Base | **Domain:** Code & Configuration Repair |
| **Storage:** SQLite (`tickets.db`) | **Storage:** Persistent Vector Store | **Storage:** Local Source Directory (`/src`) |
| **Tools:**<br>• `list_open_tickets`<br>• `get_ticket_details` | **Tools:**<br>• `search_resolutions` | **Tools:**<br>• `apply_code_patch` |
| **Resources:**<br>*(None)* | **Resources:**<br>• `chroma://resolutions/latest` | **Resources:**<br>*(None)* |
| **Prompts:**<br>• `incident_rca(ticket_id)` | **Prompts:**<br>*(None)* | **Prompts:**<br>*(None)* |
| **Security Boundary:**<br>Standard Read Queries | **Security Boundary:**<br>Standard Vector Lookups | **Security Boundary:**<br>🚨 **Human-in-the-Loop (HITL)** |



### 1. Server 1: SQL Tickets (`server_sql.py`) — Port 8001
* **Role:** Manages live relational data (open customer support/incident tickets).
* **Storage:** SQLite (`<tempdir>/mcp_ex1/sql/tickets.db`)
* **Exposed Primitives:**
  * `list_open_tickets` *(Tool)* — Fetches active incidents.
  * `get_ticket_details` *(Tool)* — Queries ticket specifics by ID.
  * `incident_rca(ticket_id)` *(Prompt)* — Builds a closing RCA summary from live ticket context.

### 2. Server 2: ChromaDB Resolutions (`server_chroma.py`) — Port 8002
* **Role:** Vector database providing semantic search (RAG) over historical resolutions. Runs 100% locally with zero external API dependencies.
* **Storage:** Persistent Vector Index (`<tempdir>/mcp_ex1/chroma`)
* **Exposed Primitives:**
  * `chroma://resolutions/latest` *(Resource)* — Passive stream of recently indexed resolutions.
  * `search_resolutions` *(Tool)* — Performs semantic vector search from an incident description.

### 3. Server 3: Patch Executor (`server_patch.py`) — Port 8003
* **Role:** Modifies local code/config files to remediate bugs.
* **Storage:** Source Workspace (`<tempdir>/mcp_ex1/src/`)
* **Exposed Primitives:**
  * `apply_code_patch` *(Tool)* — Overwrites source/configuration files. **Triggers HITL security check.**

---

## Incident RCA Prompt Flow

The client now acts as the central orchestrator:

```
                  ┌─────────────────────────────────────────┐
                  │       Central Orchestrator Client       │
                  └────────────────────┬────────────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            │ STEP 1 & 2               │ STEP 3                   │ STEP 4 & 5
            ▼                          ▼                          ▼
┌─────────────────────────┐┌─────────────────────────┐┌─────────────────────────┐
│     Server 1: SQL       ││   Server 2: ChromaDB    ││    Server 3: Patch      │
│  (Port 8001 | Tickets)  ││ (Port 8002 | Knowledge) ││  (Port 8003 | Repair)   │
└───────────┬─────────────┘└───────────┬─────────────┘└───────────┬─────────────┘
            │                          │                          │
            │ 1. TOOL:                 │                          │
            │    list_open_tickets()   │                          │
            ├──────────────────────────┼──────────────────────────┤
            │                          │                          │
            │ 2. TOOL:                 │                          │
            │    get_ticket_details()  │                          │
            ├──────────────────────────┼──────────────────────────┤
            │                          │                          │
            │                          │ 3. TOOL / RESOURCE:      │
            │                          │    search_resolutions()  │
            │                          │    chroma://resolutions  │
            ├──────────────────────────┼──────────────────────────┤
            │                          │                          │
            │                          │                          │ 4. TOOL:
            │                          │                          │    apply_code_patch()
            │                          │                          │    └── 🚨 HITL GATE
            │                          │                          │        (Client Intercept)
            ├──────────────────────────┼──────────────────────────┤
            │                          │                          │
            │ 5. PROMPT:               │                          │
            │    incident_rca()        │                          │
            │    (Generates Report)    │                          │
            ▼                          ▼                          ▼
```

The client now acts as the central orchestrator: it discovers open tickets, inspects one, searches historical fixes in ChromaDB, gates the patch through HITL, and only then fetches `incident_rca()` from Server 1 to generate the closing report.

## Key Protocol Concepts Taught in This Lab

### Tools vs. Resources
| Feature | MCP Resources | MCP Tools |
| :--- | :--- | :--- |
| **Protocol Primitive** | `chroma://resolutions/latest` | `search_resolutions(description)` |
| **Nature** | **Passive Context.** Read-only data stream attached to the model's context window. | **Active Execution.** Function called dynamically by the LLM with arguments. |
| **Side Effects** | **None.** Idempotent (like HTTP `GET`). | **Possible.** Can alter state or trigger external API calls. |

### Human-In-The-Loop (HITL) Security Interceptor

Write operations (`apply_code_patch`) can produce irreversible side effects. The client intercepts execution requests
for sensitive tools and pauses runtime execution, requiring interactive approval before passing the request over the SSE stream:

🚨 HUMAN-IN-THE-LOOP SECURITY GATE INITIATED
Action: Modify production file on Patch_Executor
Target File: db_config.json
Proposed Content:
{ "connection_timeout_ms": 5000 }
Authorize this system patch? (y/N):


Open three terminals
python server_sql.py
python server_chroma.py
python server_patch.py

Run the client orchestration
python client.py --disable-hitl

To bypass the approval prompt in automation, use `--disable-hitl` or set `MCP_DISABLE_HITL=1`.

When you run python client.py, the following sequence takes place:

1. Ticket discovery: Calls `list_open_tickets()` on Server 1 to find the active incidents.

2. Ticket inspection: Processes each open ticket returned by Server 1 one at a time.

3. Knowledge lookup: Calls `search_resolutions()` and reads `chroma://resolutions/latest` on Server 2.

4. Remediation: The client sends `apply_code_patch` to Server 3 when a vector match exists, otherwise it updates the ticket to `REQUIRE_HUMAN_FIX`.

5. RCA summary: Calls `incident_rca(ticket_id)` on Server 1 after remediation or escalation to generate the closing report.

6. Verification: Inspect the generated patch target file to confirm execution:

```shell
# Linux/macOS:
cat $TMPDIR/mcp_ex1/src/db_config.json

# Windows PowerShell:
Get-Content $env:TEMP\mcp_ex1\src\db_config.json
```

```
<system_temp_dir>/mcp_ex1/
├── sql/
│   └── tickets.db
├── chroma/
│   └── (chromadb sqlite & index files)
└── src/
    └── db_config.json

```

Find the process ids for running servers 
ps -ef | rg 'server_sql.py|server_chroma.py|server_patch.py'