
This lab repository demonstrates the Model Context Protocol (MCP) using a decoupled, multi-server microservice architecture. It provides a complete, hands-on example of how an LLM or Orchestrator Client interacts across multiple protocol primitives (Tools, Resources, and Prompts) with Server-Sent Events (SSE) and Human-in-the-Loop (HITL) security gates.


## System Architecture

Instead of a monolithic server, this lab separates concerns into three distinct MCP microservices running over independent SSE ports:

| 🗄️ Server 1: SQL Tickets | 🔍 Server 2: ChromaDB Resolutions | 🛠️ Server 3: Patch Executor |
| :--- | :--- | :--- |
| **Port:** `8001` | **Port:** `8002` | **Port:** `8003` |
| **Domain:** Live Support & Ticket Lifecycle | **Domain:** Vector Search & Knowledge Base | **Domain:** Code & Configuration Repair |
| **Storage:** SQLite (`tickets.db`) | **Storage:** Persistent Vector Store | **Storage:** Local Source Directory (`/src`) |
| **Tools:**<br>• `list_open_tickets`<br>• `get_ticket_details`<br>• `save_patch_details` | **Tools:**<br>• `search_resolutions` | **Tools:**<br>• `list_source_files(application_name, host_name="localhost")`<br>• `get_current_file(application_name, filename, host_name="localhost")`<br>• `apply_file_changes` |
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
  * `list_source_files(application_name, host_name="localhost")` *(Tool)* —
    Lists source paths for one application on one host.
  * `get_current_file(application_name, filename, host_name="localhost")`
    *(Tool)* — Returns one file from that application and host.
  * `apply_file_changes` *(Tool)* — Applies a multi-file create/update/delete set. **Triggers HITL security check.**

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
            │                          │                          │    apply_file_changes()
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

Write operations (`apply_file_changes`) can produce irreversible side effects. The client intercepts execution requests
for sensitive tools and pauses runtime execution, requiring interactive approval before passing the request over the SSE stream:

🚨 HUMAN-IN-THE-LOOP SECURITY GATE INITIATED
Action: Modify production file on Patch_Executor
Proposed File Changes:
[{"application_name": "billing", "host_name": "localhost",
  "filename": "config.py", "operation": "update", "content": "..."}]
Authorize this system patch? (y/N):


Start all three MCP servers in the foreground. Keep this terminal open; press
Ctrl-C to stop the script and all three servers:

```shell
./servers.sh start
```

You can also stop them from another terminal:

```shell
./servers.sh stop
```

Use `./servers.sh restart` to restart all three. Logs and PID files are stored
under `<tempdir>/mcp_ex1/run/`.

Restart all three servers after changing their MCP tools so bootstrap can
discover the reset tools before it clears and reseeds records.

Run the client orchestration
The client loads `OPENAI_API_KEY` from the repository `.env` file. The patch
proposal uses `gpt-4o-mini` by default; set `MCP_LLM_MODEL` to choose another
compatible OpenAI chat model.

```shell
python client.py --disable-hitl
```

To bypass the approval prompt in automation, use `--disable-hitl` or set `MCP_DISABLE_HITL=1`.

When you run `python client.py`, bootstrap clears SQL ticket and patch-history
records, Chroma resolution records, and the disposable
`<tempdir>/mcp_ex1/src` workspace, then seeds an API rolling-window rate-limit
incident, a matching historical resolution, and a small multi-module source
tree for the `api-gateway` and `rate-limiter` applications on `localhost`.
Tickets can list multiple application/host targets. The client uses those
targets to discover and fetch current source context; its remediation prompt
does not branch on this example's error code or filenames. The following
sequence takes place:

1. Ticket discovery: Calls `list_open_tickets()` on Server 1 to find the active incidents.

2. Ticket inspection: Processes each open ticket returned by Server 1 one at a time.

3. Knowledge lookup: Calls `search_resolutions()` and reads `chroma://resolutions/latest` on Server 2.

4. Remediation: For every application listed on the ticket, the client lists
   files through Server 3 and fetches each current file through
   `get_current_file(application_name, filename, host_name)`. It combines their
   contents with previous patches from SQL and matching resolution notes from
   ChromaDB in a generic OpenAI request. It applies the
   validated `PatchProposal`, which can create, update, or delete multiple
   files. The change set is saved in `Ticket.patch_details`; it is not a
   property of the incident's identity or initial ticket details.

5. RCA summary: Calls `incident_rca(ticket_id)` on Server 1 after a patch is
   successfully applied and saved, generates the RCA with the LLM, then stores
   the report on the same ticket.

The ticket row stores patch details (a list of file operations, each scoped to
an application and host), patch status
and any error message, plus the generated RCA report. `patch_status: SUCCESS`
means the change set was applied and saved, not that runtime behavior passed
verification. After a successful patch and saved RCA, the ticket moves to
`PATCHED_PENDING_VERIFICATION`. Applied file operations also remain in the
`patch_history` audit table.

6. Verification: Inspect each file listed in the ticket's
   `patch_details.changes` to confirm execution. File operations include the
   application, host, filename, action, and complete content for
   create/update.

```shell
# Linux/macOS:
cat $TMPDIR/mcp_ex1/src/localhost/rate-limiter/api/rate_limit.py

# Windows PowerShell:
Get-Content $env:TEMP\mcp_ex1\src\localhost\rate-limiter\api\rate_limit.py
```

```
<system_temp_dir>/mcp_ex1/
├── sql/
│   └── tickets.db
├── chroma/
│   └── (chromadb sqlite & index files)
└── src/
    └── localhost/
        ├── api-gateway/
        │   └── api/
        │       └── gateway.py
        └── rate-limiter/
            └── api/
                └── rate_limit.py

```

Find the process ids for running servers 
ps -ef | rg 'server_sql.py|server_chroma.py|server_patch.py'
