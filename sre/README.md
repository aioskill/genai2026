# Linux SRE MCP Gateway

A typed Model Context Protocol (MCP) gateway for inspecting and safely managing Linux servers over restricted SSH. The server exposes separate tool modules for fleet health, file inspection, configuration editing, systemd, users, security, and automation.

## Prerequisites

- Python 3.12 or newer
- SSH client (`ssh`) installed locally
- Network access from the gateway host to managed Linux nodes
- An SSH account on each node, preferably a restricted account such as `mcp-agent`
- Pinned SSH host keys in a `known_hosts` file

The default configuration targets documentation-only example addresses and keeps those nodes disabled.

## Install

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Configure managed servers

Edit [server/config.yaml](server/config.yaml).

Replace each example under `fleet_inventory.servers`:

```yaml
fleet_inventory:
  servers:
    - id: "web-01"
      host: "10.10.10.21"
      port: 22
      tags: ["env:staging", "role:web"]
      platform: "ubuntu"
      enabled: true
```

Also review:

- `gateway.ssh_user`
- `ssh.known_hosts_path`
- `ssh.strict_host_key_checking`
- `gateway.allowed_roots`
- `gateway.denied_paths`
- `gateway.denied_patterns`
- SSH timeout and concurrency limits

Do not disable strict host-key checking in production. The configured SSH user should have only the commands required by the gateway through a reviewed sudoers policy or privileged wrapper scripts.

Validate SSH access before starting the MCP server:

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes mcp-agent@10.10.10.21 /usr/bin/uptime
```

## Start the server

The server exposes MCP over SSE and binds to `127.0.0.1:8000` from `server/config.yaml`:

```bash
python -m server.main --config server/config.yaml
```

The server uses `gateway.host` and `gateway.port` from `server/config.yaml` (default `127.0.0.1:8000`). Override them at launch with `--host` and `--port` when needed.

The configuration path can also be supplied through `SRE_CONFIG`:

```bash
SRE_CONFIG=/etc/mcp-gateway/config.yaml python -m server.main
```

## Tool modules

All server code lives under [server/](server/):

| Module | Scope |
| --- | --- |
| `tools_fleet.py` | Managed-server inventory, health, and disk usage |
| `tools_files.py` | Directory, file, grep, journal, activity, and scheduled-task queries |
| `tools_config.py` | Configuration edit previews |
| `tools_systemd.py` | Systemd inspection and guarded lifecycle operations |
| `tools_users.py` | User inspection and guarded lifecycle previews |
| `tools_security.py` | Vulnerability, CVE, and reboot checks plus guarded patch previews |
| `tools_automation.py` | Approved playbook discovery and guarded automation previews |

The implementation registers 34 typed MCP tools. Tools that target nodes require exactly one of `server_id` or `tags`.

## Safety behavior

- Example nodes are disabled by default.
- File operations are restricted to configured allowed roots.
- Sensitive paths and filename patterns are denied (always enforced).
- The allowed-roots boundary can be bypassed with `gateway.enforce_path_sandbox: false` (currently disabled; full HITL approval is a Phase 2 goal).
- Paths outside the allowed roots can be granted runtime access only via the `approve_path_access` tool (HITL); approvals are recorded to the audit log and can be listed/revoked with `list_approved_paths` / `revoke_path_access`. Denied paths can never be approved.
- Read operations execute through argumentized SSH commands.
- Mutating operations default to `dry_run: true`.
- Active configuration, systemd, user, CVE, package, and playbook mutations are blocked until approved privileged wrappers are configured.
- Host-key mismatches and SSH authentication failures are not automatically retried.
- Fleet requests are bounded by configured node and concurrency limits.

This repository currently provides the MCP interface and guarded execution foundation. Persistent scheduling, production audit storage, approval-token validation, and privileged mutation wrappers must be completed and reviewed before enabling destructive operations.

## Implementation roadmap

**Phase 1 (current):** read-only fleet, file, systemd, user, security, and automation tooling; guarded dry-run previews for all mutations; argumentized SSH; SSH host-key pinning; and the universal response envelope.

**Phase 2 (next):** deferred execution. Implement `schedule` parameter handling (`run_at`, `delay`, `maintenance_window`, `auto_defer_if_outside_window`) on all mutating tools across the systemd, user, config, security, and automation domains, backed by the SQLite scheduler store with the durable `PENDING -> CLAIMED -> RUNNING -> SUCCEEDED | FAILED | CANCELLED` state machine described in `SRE_SPECS.md` §3 and §7.3. Follows the reliability, retention, and failover contracts in §7.

## Checks

Run the available static checks from the repository root:

```bash
python -m py_compile server/*.py
python -m server.main --help
```

Verify that all tools register:

```bash
python - <<'PY'
from server.main import create_server

mcp = create_server("server/config.yaml")
print(len(mcp._tool_manager._tools), "tools registered")
PY
```

## Interactive MCP terminal client

The repository includes [client/mcp_cli.py](client/mcp_cli.py), an interactive terminal client modeled on the conversation example. It connects to the MCP server over SSE (default `http://127.0.0.1:8000/sse`), discovers the available tools, sends user requests to an OpenAI model, executes requested MCP tools, and returns the tool results to the model for a final answer.

Set the model credentials and start the client:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-4.1-mini"
./start_cli.sh
```

Useful commands inside the client:

- `/help` lists interactive commands and available categories.
- `/help systemd` prints help for one tool category; aliases such as `/help services` are supported.
- `/tools` lists all discovered MCP tools.
- `/reset` starts a new model context while keeping the MCP connection.
- `/exit` or `/quit` closes the client and server subprocess.

Options can be passed directly or through the launcher:

```bash
./start_cli.sh --config server/config.yaml --model gpt-4.1-mini
```

The client stores prompt history in `.mcp_prompt_history`. Do not commit that file if it contains sensitive operational questions.

## Logging

The gateway logs to the console and rotating JSON log files configured under `gateway` in `server/config.yaml`:

- `./var/mcp-gateway.log` — gateway and tool request logs
- `./var/audit.log` — tool audit events

Each tool request records its tool name, target type, status, duration, and error code when applicable. Unexpected failures receive an `error_id`; request arguments and secrets are not logged. Log files rotate at 10 MiB with five backups.

## Error handling

Tool failures are returned as the standard MCP error envelope with `status: "error"`, a stable error code, and a safe message. Invalid targeting, unknown servers, denied paths, SSH failures, timeouts, and disabled mutations are handled without terminating the MCP server. Unexpected failures are logged with an `error_id` that can be given to the operator.

## Project specification

See [SRE_SPECS.md](SRE_SPECS.md) for the complete gateway contract, security model, targeting rules, risk tiers, audit requirements, and operational reliability requirements.


Stop running server
 pkill -f "server\.ma[n]"