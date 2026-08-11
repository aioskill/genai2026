# Linux SRE MCP Gateway: Technical Specification & Contract

**Document Version:** 1.0.0

**Target Audience:** Engineering Leadership, SRE Teams & Architecture Board

**Scope:** Model Context Protocol (MCP) Infrastructure Proxy Interface

**Deployment Model:** Gateway Proxy with Agentless SSH Node Orchestration

---

## 1. Executive Summary & System Architecture

The **Linux SRE MCP Gateway** acts as an audited, authenticated proxy enabling Large Language Models (LLMs) and AI Agents to safely inspect, manage, and automate enterprise Linux infrastructure.

```
┌──────────────────┐            MCP Protocol (Stdio / SSE)            ┌──────────────────────────┐
│   MCP Host App   │ <===============================================> │   MCP Gateway Proxy      │
│ (LLM Controller) │                                                   │  (Python + FastMCP)      │
└──────────────────┘                                                   └────────────┬─────────────┘
                                                                                    │
                                                     ┌──────────────────────────────┴──────────────────────────────┐
                                                     │ Restricted SSH (Ed25519) + Sudoers Command Whitelist       │
                                                     ▼                                                             ▼
                                          ┌────────────────────┐                                        ┌────────────────────┐
                                          │ Target Linux Node A│                                        │ Target Linux Node B│
                                          │   (192.168.1.10)   │                                        │   (192.168.1.20)   │
                                          └────────────────────┘                                        └────────────────────┘

```

### Key Design Pillars

1. **Flexible Node Targeting (`server_id` OR `tags`):** All multi-node interactions accept either a specific `server_id` or a array of metadata `tags` for multi-node execution, keeping host routing distinct from model prompts.
2. **Least Privilege Access:** Eliminates arbitrary shell execution (`run_command`) in favor of 31 discrete, strongly-typed tools with parameter validation.
3. **Defense-in-Depth Safety:** Mutating tools default to `dry_run: true`, perform automatic backups, enforce path sandboxing, support deferred execution windows, and log to an immutable audit file.

---

## 2. Universal API Envelope Standard

Every tool call executed by the MCP Gateway returns a standardized response envelope to ensure predictable model behavior and simplified parsing.

### Universal Single / Multi-Node Response Contract

| Response Field | Type | Required | Description |
| --- | --- | --- | --- |
| **`status`** | String | **Yes** | Execution result state: `success`, `error`, `dry_run_preview`, or `scheduled`. |
| **`target_type`** | String | **Yes** | Selector type used: `"single"` (via `server_id`) or `"multi_tag"` (via `tags`). |
| **`server_id`** | String | Conditional | Target server identifier (present when `target_type` is `"single"`). |
| **`matching_nodes`** | Array[String] | Conditional | List of resolved server IDs (present when `target_type` is `"multi_tag"`). |
| **`dry_run`** | Boolean | **Yes** | Indicates whether payload represents a dry-run preview (`true`) or active mutation (`false`). |
| **`summary`** | Object | Conditional | Counters for multi-node runs: `total_nodes`, `succeeded_nodes`, `failed_nodes`. |
| **`data`** | Object | Conditional | Output data dictionary for single-node execution. |
| **`results`** | Object | Conditional | Mapping of `server_id` -> individual result objects for multi-node execution. |
| **`schedule_metadata`** | Object | Conditional | Present when `status` is `"scheduled"`. Details execution ETA and policy reason. |
| **`error`** | Object | Conditional | Contains error metadata (`code`, `message`) if `status` is `error`. |

---

## 3. Global Targeting & Deferred Execution Contracts

All 31 tools share a standardized set of target selection and execution parameters.

### Flexible Targeting Schema

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`server_id`** | String | Conditional | — | Target single server identifier (e.g., `web-01`). *Mutually exclusive with `tags`.* |
| **`tags`** | Array[String] | Conditional | — | Target nodes matching metadata tags (e.g., `["role:web", "env:prod"]`). Executed in parallel. *Mutually exclusive with `server_id`.* |
| **`concurrency`** | Integer | No | `10` | Maximum parallel SSH execution workers when using `tags` (Maximum: `50`). |

> **Validation Logic (Gateway Layer 1):** `REQUIRED: exactly_one_of(["server_id", "tags"])`. Failing to provide exactly one selector results in `INVALID_TARGETING_SPEC`.

### Universal Deferred Execution Schema (`schedule`)

Mutating tools (`is_mutating: true`) accept an optional `schedule` parameter block to defer operations to maintenance windows or specific timestamps.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`schedule.run_at`** | String (ISO 8601) | Conditional | — | Absolute UTC timestamp (e.g., `2026-08-12T02:00:00Z`). *Mutually exclusive with `delay`.* |
| **`schedule.delay`** | String | Conditional | — | Relative delay duration (e.g., `30m`, `2h`). *Mutually exclusive with `run_at`.* |
| **`schedule.maintenance_window`** | String | Conditional | — | Named policy window (e.g., `"prod-nightly-window"`). Resolves to next open window. |
| **`schedule.auto_defer_if_outside_window`** | Boolean | No | `true` | Automatically defers execution if current time falls outside server maintenance window. |

---

## 4. Master Tool Catalog (31 Tools across 7 Domains)

---

### Category A: Fleet & System Health (Read-Only)

Provides visibility into infrastructure health, load averages, memory consumption, and disk space usage across target nodes.

#### A.1 `list_managed_servers`

Lists all registered Linux servers available in the gateway inventory.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| *(None)* | — | — | — | Returns host inventory, IP mappings, tags, and target roles. |

* **Mutating:** `false` | **Supports Dry-Run:** `false` | **HITL Confirmation:** Not Required

#### A.2 `get_system_health`

Retrieves CPU load, memory usage, swap, and uptime metrics across target hosts.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`server_id`** / **`tags`** | String / Array | **Yes** | — | Single server ID or tag selector array. |

* **Mutating:** `false` | **Supports Dry-Run:** `false` | **HITL Confirmation:** Not Required

#### A.3 `get_disk_usage`

Checks filesystem utilization, available bytes, and inode counts across mount points.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`server_id`** / **`tags`** | String / Array | **Yes** | — | Single server ID or tag selector array. |
| **`mount_point`** | String | No | `/` | Target mount point to inspect (e.g., `/`, `/var`). |

* **Mutating:** `false` | **Supports Dry-Run:** `false` | **HITL Confirmation:** Not Required

---

### Category B: File Inspection, Logging & Task Discovery (Read-Only)

Provides sandboxed inspection of host directories, logs, task activity history, and scheduled jobs.

#### B.1 `list_directory`

Scans directory contents safely with path sandboxing and recursion depth caps.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`server_id`** / **`tags`** | String / Array | **Yes** | — | Target selector. |
| **`path`** | String | **Yes** | — | Absolute directory path (e.g., `/var/log`). |
| **`recursive`** | Boolean | No | `false` | Enable recursive scanning. |
| **`max_depth`** | Integer | No | `2` | Max recursion depth allowed (Maximum: `5`). |

* **Mutating:** `false` | **Supports Dry-Run:** `false` | **HITL Confirmation:** Not Required

#### B.2 `read_file_head_tail`

Reads top or bottom lines of a target text file within strict line bounds.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`server_id`** / **`tags`** | String / Array | **Yes** | — | Target selector. |
| **`path`** | String | **Yes** | — | Absolute file path. |
| **`mode`** | String | No | `tail` | Read location: `head` or `tail`. |
| **`lines`** | Integer | No | `50` | Number of lines to retrieve (Maximum: `500`). |

* **Mutating:** `false` | **Supports Dry-Run:** `false` | **HITL Confirmation:** Not Required

#### B.3 `grep_file`

Searches inside target text/log files using regular expressions.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`server_id`** / **`tags`** | String / Array | **Yes** | — | Target selector. |
| **`path`** | String | **Yes** | — | Absolute path to file. |
| **`pattern`** | String | **Yes** | — | Regular expression pattern. |
| **`max_matches`** | Integer | No | `100` | Max matching lines to return (Maximum: `500`). |

* **Mutating:** `false` | **Supports Dry-Run:** `false` | **HITL Confirmation:** Not Required

#### B.4 `read_journal_logs`

Queries systemd journal logs (`journalctl`) filtered by service unit and log severity.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`server_id`** / **`tags`** | String / Array | **Yes** | — | Target selector. |
| **`unit_name`** | String | **Yes** | — | Systemd unit name (e.g., `nginx`, `postgresql`). |
| **`since`** | String | No | `1h` | Relative time filter (e.g., `15m`, `2h`, `1d`). |
| **`priority`** | String | No | `info` | Severity (`emerg`, `alert`, `crit`, `err`, `warning`, `notice`, `info`, `debug`). |
| **`lines`** | Integer | No | `100` | Max lines to return (Maximum: `500`). |

* **Mutating:** `false` | **Supports Dry-Run:** `false` | **HITL Confirmation:** Not Required

#### B.5 `get_activity_logs`

Queries operational history, task step progress, and execution status across tasks.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`task_id`** | String | No | — | Filter by specific background task UUID. |
| **`server_id`** / **`tags`** | String / Array | No | — | Filter activity logs by server ID or tags. |
| **`tool_name`** | String | No | — | Filter by tool name (e.g., `run_system_patching`). |
| **`status`** | String | No | `all` | Filter state: `running`, `completed`, `failed`, `cancelled`, `all`. |
| **`since`** | String | No | `1h` | Duration filter (e.g., `15m`, `24h`, `7d`). |
| **`limit`** | Integer | No | `50` | Maximum log records (Maximum: `200`). |

* **Mutating:** `false` | **Supports Dry-Run:** `false` | **HITL Confirmation:** Not Required

#### B.6 `list_scheduled_tasks`

Queries pending or recurring deferred tasks across nodes or tagged clusters.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`server_id`** / **`tags`** | String / Array | No | — | Filter scheduled tasks by server ID or tags. |
| **`status`** | String | No | `pending` | Task filter: `pending`, `executing`, `completed`, `cancelled`, `all`. |

* **Mutating:** `false` | **Supports Dry-Run:** `false` | **HITL Confirmation:** Not Required

---

### Category C: Configuration Editing (Mutating)

Supports text edits inside configuration files with automated backups and diff previews.

#### C.1 `insert_text_block`

Inserts multi-line configuration blocks relative to an anchor pattern in a file.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`server_id`** / **`tags`** | String / Array | **Yes** | — | Target selector. |
| **`path`** | String | **Yes** | — | Absolute path to config file. |
| **`text_block`** | String | **Yes** | — | Multi-line text block to insert. |
| **`anchor_pattern`** | String | No | — | Regex pattern used as insertion anchor. |
| **`position`** | String | No | `after` | Insertion position: `before`, `after`, `top`, `bottom`. |
| **`dry_run`** | Boolean | No | `true` | Returns unified diff preview without writing. |
| **`create_backup`** | Boolean | No | `true` | Creates timestamped `.bak` copy prior to writing. |
| **`schedule`** | Object | No | — | Optional deferred execution parameters. |

* **Mutating:** `true` | **Supports Dry-Run:** `true` | **HITL Confirmation:** Required (Tier 2)

#### C.2 `replace_text_regex`

Performs regex search and replacement inside configuration files.

| Parameter | Type | Required | Default | Constraint / Description |
| --- | --- | --- | --- | --- |
| **`server_id`** / **`tags`** | String / Array | **Yes** | — | Target selector. |
| **`path`** | String | **Yes** | — | Absolute path to target file. |
| **`pattern`** | String | **Yes** | — | Regex search pattern. |
| **`replacement`** | String | **Yes** | — | Replacement string (supports capture groups). |
| **`max_replacements`** | Integer | No | `1` | Max substitution count (`0` for global replace). |
| **`dry_run`** | Boolean | No | `true` | Returns unified diff preview without writing. |
| **`create_backup`** | Boolean | No | `true` | Creates timestamped `.bak` copy prior to writing. |
| **`schedule`** | Object | No | — | Optional deferred execution parameters. |

* **Mutating:** `true` | **Supports Dry-Run:** `true` | **HITL Confirmation:** Required (Tier 2)

---

### Category D: Systemd Service Lifecycle Management

Manages background services, daemon reload cycles, and unit file deployments.

#### Systemd Tools Summary Table

| Tool Name | Operation Description | Target Parameters | Mutating | Dry-Run | HITL Tier |
| --- | --- | --- | --- | --- | --- |
| **`systemd_service_exists`** | Verifies unit existence & enablement status. | `server_id` OR `tags`, `service_name` | `false` | `false` | None |
| **`get_service_status`** | Fetches active state, PID, & health metrics. | `server_id` OR `tags`, `service_name` | `false` | `false` | None |
| **`add_systemd_service`** | Provisions a new unit in `/etc/systemd/system/`. | `server_id` OR `tags`, `service_name`, `unit_content`, `enable_on_boot` (`default: true`), `dry_run` (`default: true`), `schedule` | `true` | `true` | Tier 2 |
| **`remove_systemd_service`** | Stops, disables, and deletes unit file. | `server_id` OR `tags`, `service_name`, `dry_run` (`default: true`), `schedule` | `true` | `true` | Tier 3 |
| **`start_systemd_service`** | Starts an inactive systemd unit. | `server_id` OR `tags`, `service_name`, `schedule` | `true` | `false` | Tier 2 |
| **`stop_systemd_service`** | Stops an active systemd unit. | `server_id` OR `tags`, `service_name`, `schedule` | `true` | `false` | Tier 3 |
| **`restart_systemd_service`** | Restarts an active or failed service unit. | `server_id` OR `tags`, `service_name`, `schedule` | `true` | `false` | Tier 2 |
| **`reload_systemd_service`** | Reloads service config without process restart. | `server_id` OR `tags`, `service_name`, `schedule` | `true` | `false` | Tier 2 |

---

### Category E: User & Access Management

Controls system user provisioning, account lifecycle states, login inspection, and SSH key management.

#### User Management Tools Specification

| Tool Name | Description | Key Parameters | Mutating | Dry-Run | HITL Tier |
| --- | --- | --- | --- | --- | --- |
| **`list_system_users`** | Lists accounts, UIDs, primary groups, and lock states. | `server_id` OR `tags` | `false` | `false` | None |
| **`get_recent_logins`** | Queries login history (`wtmp`, `btmp`) and active SSH sessions. | `server_id` OR `tags`, `login_type` (`successful`, `failed`, `currently_logged_in`, `all`), `username`, `limit` | `false` | `false` | None |
| **`create_system_user`** | Creates user, home directory, groups, and SSH keys. | `server_id` OR `tags`, `username`, `groups`, `ssh_public_key`, `dry_run` (`default: true`), `schedule` | `true` | `true` | Tier 2 |
| **`disable_system_user`** | Locks password, sets shell to `/sbin/nologin`, terminates processes. | `server_id` OR `tags`, `username`, `terminate_processes` (`default: true`), `dry_run` (`default: true`), `schedule` | `true` | `true` | Tier 3 |
| **`enable_system_user`** | Unlocks password and restores login shell. | `server_id` OR `tags`, `username`, `schedule` | `true` | `false` | Tier 2 |
| **`remove_system_user`** | Deletes account with optional home directory archiving. | `server_id` OR `tags`, `username`, `archive_home` (`default: true`), `dry_run` (`default: true`), `schedule` | `true` | `true` | Tier 3 |

---

### Category F: Security & Vulnerability Management

Provides vulnerability detection, CVE correlation, and patch application workflows.

| Tool Name | Description | Key Parameters | Mutating | Dry-Run | HITL Tier |
| --- | --- | --- | --- | --- | --- |
| **`scan_vulnerabilities`** | Scans host for unpatched packages and security advisories. | `server_id` OR `tags`, `severity_threshold` (`low`, `medium`, `high`, `critical`) | `false` | `false` | None |
| **`check_cve_status`** | Evaluates host exposure against a specific CVE ID. | `server_id` OR `tags`, `cve_id` (e.g., `CVE-2024-3094`) | `false` | `false` | None |
| **`patch_cve`** | Installs targeted package updates to resolve specific CVEs. | `server_id` OR `tags`, `cve_id`, `dry_run` (`default: true`), `schedule` | `true` | `true` | Tier 2 |
| **`check_reboot_required`** | Checks if security updates require an OS reboot. | `server_id` OR `tags` | `false` | `false` | None |

---

### Category G: Automation, Ansible & Task Management

Interface for executing vetted Ansible playbooks and managing background operations.

| Tool Name | Description | Key Parameters | Mutating | Dry-Run | HITL Tier |
| --- | --- | --- | --- | --- | --- |
| **`list_available_playbooks`** | Enumerates approved playbooks stored on Gateway. | *(None)* | `false` | `false` | None |
| **`run_system_patching`** | Executes baseline OS patching playbook. | `server_id` OR `tags`, `reboot_if_needed` (`default: false`), `dry_run` (`default: true`), `schedule` | `true` | `true` | Tier 2 |
| **`run_package_installer`** | Installs/updates packages via standard Ansible roles. | `server_id` OR `tags`, `packages` (list), `state` (`present`, `latest`, `absent`), `dry_run` (`default: true`), `schedule` | `true` | `true` | Tier 2 |
| **`execute_playbook`** | Runs approved playbook with structured variable inputs. | `server_id` OR `tags`, `playbook_name`, `extra_vars` (dict), `dry_run` (`default: true`), `schedule` | `true` | `true` | Tier 2 |
| **`cancel_scheduled_task`** | Cancels a deferred task prior to execution ETA. | `task_id`, `reason` | `true` | `false` | Tier 2 |

---

## 5. Gateway Configuration Schema (`/etc/mcp-gateway/config.yaml`)

The MCP Gateway operates according to a centralized YAML configuration defining maintenance windows, deferral policies, tag mappings, and scheduler rules:

```yaml
version: "1.0.0"
gateway:
  id: "mcp-gateway-prod-01"
  environment: "production"
  timezone: "UTC"
  log_level: "INFO"
  audit_log_path: "/var/log/mcp-gateway/audit.log"

# ==============================================================================
# 1. DEPLOYMENT WINDOWS & MAINTENANCE SCHEDULES
# ==============================================================================
maintenance_windows:
  - id: "prod-nightly-window"
    name: "Production Nightly Off-Peak Window"
    description: "Low-traffic period for routine patches and non-disruptive restarts."
    schedule:
      cron: "0 2 * * *" # Daily at 02:00 UTC
      duration: "3h"     # Window active 02:00 UTC to 05:00 UTC
    allowed_risk_tiers: ["Tier1", "Tier2"]

  - id: "weekend-maintenance-window"
    name: "Weekend Infrastructure Maintenance Window"
    description: "Approved window for high-risk mutations, kernel upgrades, and user purging."
    schedule:
      cron: "0 0 * * 0" # Every Sunday at 00:00 UTC
      duration: "6h"     # Window active 00:00 UTC to 06:00 UTC
    allowed_risk_tiers: ["Tier1", "Tier2", "Tier3"]

  - id: "staging-anytime-window"
    name: "Staging Unrestricted Window"
    description: "Continuous maintenance window for pre-production environments."
    schedule:
      continuous: true
    allowed_risk_tiers: ["Tier1", "Tier2", "Tier3"]

# ==============================================================================
# 2. AUTOMATED DEFERRAL & EXECUTION POLICY
# ==============================================================================
deferral_policies:
  default_policy:
    enforce_maintenance_windows: true
    auto_defer_outside_window: true # Converts immediate runs to deferred tasks outside windows
    require_dry_run_first: true      # Mandatory dry-run preview before scheduling
    default_concurrency_limit: 10   # Max parallel SSH workers for tag-targeted runs

  rules:
    - name: "Strict Production Mutation Guard"
      match:
        tags: ["env:prod"]
        is_mutating: true
      behavior:
        action: "DEFER_IF_OUTSIDE_WINDOW"
        assigned_window: "prod-nightly-window"
        allow_immediate_override: false

    - name: "Critical System Service Interruption Guard"
      match:
        tools: ["remove_systemd_service", "stop_systemd_service", "remove_system_user"]
        tags: ["env:prod"]
      behavior:
        action: "REQUIRE_WINDOW_AND_TIER3_APPROVAL"
        assigned_window: "weekend-maintenance-window"
        require_approval_token: true

    - name: "Staging Pass-Through"
      match:
        tags: ["env:staging", "env:dev"]
      behavior:
        action: "ALLOW_IMMEDIATE"
        enforce_maintenance_windows: false

# ==============================================================================
# 3. TAG-BASED FLEET MAPPINGS & DEFAULTS
# ==============================================================================
fleet_inventory:
  tag_mappings:
    "env:prod":
      maintenance_window: "prod-nightly-window"
      max_concurrency: 5
      blast_radius_escalation_threshold: 5 # Escalates to Tier 3 if >5 hosts targeted
    "env:staging":
      maintenance_window: "staging-anytime-window"
      max_concurrency: 20
      blast_radius_escalation_threshold: 15
    "role:database":
      maintenance_window: "weekend-maintenance-window"
      auto_backup_mandatory: true

# ==============================================================================
# 4. DEFERRED TASK SCHEDULER ENGINE
# ==============================================================================
task_scheduler:
  poll_interval_seconds: 10
  storage:
    type: "sqlite"
    path: "/var/lib/mcp-gateway/scheduler.db"
  max_retries: 2
  retry_backoff_seconds: 300
  task_retention_days: 30 # Retains records for get_activity_logs queries

```

---

## 6. Governance, Security Controls & Audit Standard

### 6.1 Path Sandboxing Policy

All file inspection and modification tools validate input paths against strict canonical boundaries (`pathlib.Path.resolve()`).

| Policy Zone | Boundary Paths | Enforcement Action |
| --- | --- | --- |
| **Allowed Roots** | `/var/log`, `/etc`, `/opt`, `/srv`, `/tmp` | Operations permitted subject to file permissions. |
| **Denied Absolute Paths** | `/etc/shadow`, `/etc/sudoers`, `/etc/pam.d` | Execution blocked immediately by Gateway policy. |
| **Denied File Patterns** | `*.key`, `*.pem`, `*/.ssh/*`, `*id_rsa*` | Regex matcher blocks access prior to execution. |

---

### 6.2 OS Sudoers Privilege Boundaries (`/etc/sudoers.d/mcp-agent-policy`)

The remote SSH execution user (`mcp-agent`) operates under strict OS-level command whitelisting. Interactive shells and shell escape vectors are explicitly prohibited.

```sudoers
Defaults:mcp-agent !requiretty
Defaults:mcp-agent secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Defaults:mcp-agent env_reset

User_Alias MCP_USERS = mcp-agent

Cmnd_Alias SYSTEMD_READ = /bin/systemctl status *, /bin/systemctl is-active *, /bin/systemctl is-enabled *
Cmnd_Alias SYSTEMD_MUTATE = /bin/systemctl start *, /bin/systemctl stop *, /bin/systemctl restart *, /bin/systemctl reload *, /bin/systemctl daemon-reload
Cmnd_Alias USER_READ = /usr/bin/id *, /usr/bin/last *, /usr/bin/lastb *, /usr/bin/who, /usr/bin/w
Cmnd_Alias USER_MUTATE = /usr/sbin/useradd *, /usr/sbin/usermod *, /usr/sbin/userdel *, /usr/bin/pkill -u *
Cmnd_Alias PKG_MUTATE = /usr/bin/apt-get update, /usr/bin/apt-get install *, /usr/bin/apt-get remove *, /usr/bin/dnf check-update, /usr/bin/dnf update *
Cmnd_Alias FILE_MUTATE = /bin/cp *, /bin/mv *, /bin/mkdir *, /bin/tar -czf *

MCP_USERS ALL=(root) NOPASSWD: SYSTEMD_READ, SYSTEMD_MUTATE, USER_READ, USER_MUTATE, PKG_MUTATE, FILE_MUTATE

```

---

### 6.3 Human-in-the-Loop (HITL) Risk Classification Matrix

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          TIER 1: READ-ONLY                              │
│  Auto-Approved | No Side Effects | No Operator Approval Required        │
│  Examples: list_directory, get_system_health, scan_vulnerabilities       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┴─────────────────────────────────────┐
│                          TIER 2: CONTROLLED MUTATION                    │
│  Requires Operator Click Approval | Requires Dry-Run Diff Preview       │
│  Examples: restart_systemd_service, insert_text_block, patch_cve         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┴─────────────────────────────────────┐
│                          TIER 3: HIGH-RISK CRITICAL                     │
│  Requires Operator Approval + Secondary Typed Confirmation / Token      │
│  Escalated automatically when tags match > blast_radius_threshold nodes. │
│  Examples: remove_system_user, remove_systemd_service, stop_systemd_svc │
└─────────────────────────────────────────────────────────────────────────┘

```

---

### 6.4 Audit Event Telemetry Standard

Every tool request generates a structured, append-only JSON audit event logged to `syslog` (Facility: `authpriv`) and `/var/log/mcp-gateway/audit.log`:

```json
{
  "timestamp": "2026-08-11T09:04:21Z",
  "event_id": "8f23901a-4d22-4211-9a22-21a4812f8830",
  "mcp_session_id": "sess_88301923",
  "client_identity": {
    "user_id": "sre-operator@company.com",
    "client_app": "ClaudeDesktop/1.4.0"
  },
  "execution_target": {
    "target_type": "multi_tag",
    "tags": ["env:prod", "role:web"],
    "matching_nodes": ["web-01", "web-02"]
  },
  "tool_call": {
    "name": "patch_cve",
    "parameters": { "cve_id": "CVE-2024-3094", "dry_run": false },
    "is_mutating": true,
    "dry_run": false,
    "hitl_approved": true,
    "approval_token": "tok_hitl_9918230"
  },
  "execution_result": {
    "status": "SUCCESS",
    "summary": { "total_nodes": 2, "succeeded_nodes": 2, "failed_nodes": 0 },
    "execution_duration_ms": 1420
  }
}

```


---

## 7. Operational Reliability & Capacity Contract

The following requirements are mandatory production defaults. An environment may
tighten them, but may not weaken them without an approved change record.

### 7.1 Availability and latency objectives

The gateway is available when it authenticates a client, answers health probes,
and accepts a valid read-only request. Production objectives are:

| Objective | Target |
| --- | --- |
| Monthly gateway availability | 99.9%, excluding approved maintenance |
| MCP request acceptance | p95 <= 500 ms; p99 <= 2 s |
| Read-only single-node operation | p95 <= 5 s, excluding remote command time |
| Mutating-operation acknowledgement | p95 <= 2 s |
| Scheduled-task dispatch delay | p95 <= 30 s after eligibility |
| Health probe response | p99 <= 1 s |

Long-running work must be asynchronous and return a stable `task_id`. No MCP
request may remain open beyond `request_timeout_seconds` (default `30`).
Metrics must be segmented by tool, transport, target type, and result state.

### 7.2 SSH failures and unreachable nodes

Node executions are isolated. One failed node must not cancel other nodes unless
explicit `fail_fast` was requested. The gateway must expose stable error codes:

| Condition | Code | Default handling |
| --- | --- | --- |
| Inventory or DNS failure | `NODE_RESOLUTION_FAILED` | No retry; mark failed |
| Connection timeout | `SSH_CONNECT_TIMEOUT` | Retry twice with bounded backoff |
| Refused or unreachable host | `NODE_UNREACHABLE` | Retry twice, then mark failed |
| Host-key mismatch | `SSH_HOST_KEY_MISMATCH` | Never retry; security alert |
| Authentication failure | `SSH_AUTH_FAILED` | Never retry automatically |
| Remote command timeout | `REMOTE_COMMAND_TIMEOUT` | Retry only if idempotent |
| Non-zero remote exit | `REMOTE_COMMAND_FAILED` | Preserve exit code and stderr |

Defaults are a 10-second connection timeout, 120-second read-only command
timeout, 30-minute approved patch/playbook timeout, and retry delays of 5 and
30 seconds with jitter. Capture at most 1 MiB of stdout and stderr per node.

Multi-node results must include per-node state, error code, retry count, and
timestamps. Mixed results must use `partial_success`, never plain `success`.

### 7.3 Scheduler failover and duplicate prevention

Tasks use durable transitions:

`PENDING -> CLAIMED -> RUNNING -> SUCCEEDED | FAILED | CANCELLED`

Each task stores a unique `task_id`, idempotency key, operation fingerprint,
target snapshot, parameters, eligibility time, lease owner, lease expiry,
attempt count, and final result. Claiming is an atomic database operation.
Workers renew a 60-second lease; another worker may reclaim only after expiry.

Equivalent submissions with the same idempotency key return the existing task.
Reclaimed tasks must re-check target state and must not blindly repeat a
non-idempotent mutation. Audit events record attempt, lease owner, and reclaim
reason. Production requires at least two gateway instances, with failover to a
healthy standby within 90 seconds.

### 7.4 SQLite locking and backup

The SQLite scheduler store must use WAL mode, `synchronous=FULL`, foreign-key
enforcement, and a 5-second busy timeout. State transitions use short
transactions and conditional atomic updates. Migrations acquire an exclusive
lock before workers start. Database, WAL, and SHM files must share one local
filesystem. Lock waits, busy errors, WAL growth, checkpoint duration, and
failed commits are monitored.

Create a consistent backup every 15 minutes while tasks are active and hourly
otherwise. Keep hourly backups for 48 hours and daily backups for 30 days,
outside the gateway host and encrypted at rest. Test restoration monthly. RPO
is 15 minutes and RTO is 30 minutes. Restored `CLAIMED` or `RUNNING` tasks
become `RECOVERY_REVIEW_REQUIRED` until reconciled. More than one active writer
or a fleet above Section 7.9 limits requires PostgreSQL.

### 7.5 Task and audit retention

| Data | Retention |
| --- | --- |
| Scheduler detail and output | 30 days |
| Scheduler summaries | 180 days |
| Ordinary audit events | 1 year |
| Security-sensitive audit events | 2 years |
| Failed or dangerous-operation audit events | 3 years |

Audit events must be exported to append-only or WORM-capable storage before
local rotation. Retention jobs report archived, deleted, and failed records
and must honor incident holds and legal holds. Task output may be truncated or
securely archived after active retention; local deletion must not remove the
only audit copy.

### 7.6 Monitoring and alerting

Expose Prometheus-compatible metrics and structured logs for request latency,
validation failures, SSH failures, per-tool and per-node outcomes, queue age,
lease expiry/reclaims, SQLite locks/WAL/backup age, approval events, resource
limits, and gateway CPU, memory, disk, file descriptors, and worker saturation.

Alert on two failed readiness probes in two minutes, an eligible task delayed
more than two minutes, more than three lease reclaims in ten minutes, a backup
older than 30 minutes, more than 5% busy/timed-out writes for five minutes,
more than 20% SSH failures in ten minutes, any unapproved Tier 3 operation,
any host-key mismatch, any blast-radius threshold breach, and any hard resource
limit. Dangerous-operation alerts include session, operator, tool, target
snapshot, approval ID, and task ID, with secrets redacted.

### 7.7 Gateway health checks

Provide `/health/live` for process/transport liveness, `/health/ready` for
configuration, inventory, audit sink, scheduler store, and worker capacity,
and an authenticated `/health/dependencies` diagnostic endpoint. Liveness
must not depend on target-node availability. Readiness must fail when the
gateway cannot safely accept new work. Checks have a one-second timeout, must
not mutate or scan the fleet, and must expose no credentials, file contents,
approval tokens, or internal host details to unauthenticated callers.

### 7.8 Upgrade and migration procedures

Every release includes versioned gateway/configuration schemas, tool-contract
version, compatibility matrix, migration notes, rollback notes, and tested
backup/restore steps. The deployment sequence is: validate configuration; take
and verify a database backup; run migrations under exclusive lock; start a
readiness-disabled canary; verify health, metrics, audit writes, and a
read-only smoke test; shift traffic gradually; then enable scheduling and
mutations.

Migrations remain backward-compatible for one rolling-deployment window.
Destructive changes require a separate release. Irreversible rollback restores
the verified backup and reconciles tasks created after its watermark.

### 7.9 Supported platforms and capacity

The initial full-support matrix is Ubuntu 22.04/24.04 LTS and Debian 12 using
`apt-get`, plus RHEL 9, Rocky Linux 9, and AlmaLinux 9 using `dnf`. RHEL 8
derivatives are read-only unless separately certified; other distributions are
unsupported by default. Inventory registration records distribution, version,
architecture, init system, and package manager. Unsupported combinations are
rejected before mutation.

Defaults are 1,000 registered nodes per gateway, 200 nodes per tag request,
50 concurrent SSH workers per gateway, 20 per request, 25 production workers,
50 staging workers, and default tag concurrency of 10. Effective concurrency
is the minimum of request, gateway, environment, and tag limits. Requests above
hard limits fail validation unless an authorized override exists. Fleet work is
batched in groups of 20 by default; Tier 3 batch failure stops later batches
and requires review.

### 7.10 Resource limits

| Resource | Default | Hard maximum |
| --- | ---: | ---: |
| Regex pattern length | 4 KiB | 16 KiB |
| Regex time per file | 250 ms | 2 s |
| Regex time per request | 5 s | 30 s |
| Returned regex matches | 100 | 500 |
| Recursive depth | 2 | 5 |
| Directory entries | 1,000 | 10,000 |
| Files scanned recursively | 500 | 2,000 |
| Single file read | 1 MiB | 10 MiB |
| Total file data per request | 5 MiB | 50 MiB |
| Journal/log output per node | 1 MiB | 10 MiB |

Use a bounded or linear-time regex engine where available and reject constructs
that permit catastrophic backtracking. Reject binary, device, FIFO, special,
and over-limit files, or report them as skipped. Recursive scans do not follow
symlinks by default, enforce a wall-clock deadline, and return truncation
metadata. Resource-limit errors use stable codes such as `REGEX_TIMEOUT`,
`FILE_SIZE_LIMIT`, `DIRECTORY_ENTRY_LIMIT`, and `OUTPUT_TRUNCATED`; each creates
an audit event without recording file contents.
