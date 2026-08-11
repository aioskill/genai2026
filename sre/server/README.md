# Linux SRE MCP Gateway

Install dependencies with `python -m pip install -r requirements.txt`, copy and edit `server/config.yaml`, then run:

```bash
python -m server.main --config server/config.yaml
```

The default configuration has disabled example nodes. Replace them with real inventory entries, set `enabled: true`, configure the SSH user and pinned `known_hosts_path`, and review the allowed/denied paths before connecting production hosts.

## Error handling

Tool failures are returned as the standard MCP error envelope with `status: "error"`, a stable error code, and a safe message. Invalid targeting, unknown servers, denied paths, SSH failures, timeouts, and disabled mutations are handled without terminating the MCP server. Unexpected failures are logged with an `error_id` that can be given to the operator.

The current implementation exposes the read-only fleet, file, systemd, user, security, and approved-playbook discovery tools. Mutating tools default to dry-run previews; production scheduling, durable audit persistence, and privileged wrapper commands must be completed before enabling destructive operations.
