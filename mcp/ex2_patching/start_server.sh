#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

exec python3 -m server.main \
    --config "${SCRIPT_DIR}/server/config.yaml" \
    --log-level INFO \
    --host 127.0.0.1 \
    --port 8000 \
    "$@"
