#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${TMPDIR:-/tmp}/mcp_ex1/run"
mkdir -p "${RUN_DIR}"

if [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
elif [[ -x "${SCRIPT_DIR}/../../.venv/bin/python" ]]; then
    PYTHON_BIN="${SCRIPT_DIR}/../../.venv/bin/python"
else
    PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

SERVER_NAMES=(server_sql server_chroma server_patch)
SERVER_PIDS=()
CLEANING_UP=0

pid_file() {
    printf '%s/%s.pid' "${RUN_DIR}" "$1"
}

log_file() {
    printf '%s/%s.log' "${RUN_DIR}" "$1"
}

pid_is_server() {
    local pid="$1"
    local server_path="$2"
    local command

    kill -0 "${pid}" 2>/dev/null || return 1
    command="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
    [[ "${command}" == *"${server_path}"* ]]
}

start_servers() {
    local name
    local path
    local pid

    for name in "${SERVER_NAMES[@]}"; do
        path="${SCRIPT_DIR}/${name}.py"
        if [[ -f "$(pid_file "${name}")" ]]; then
            pid="$(<"$(pid_file "${name}")")"
            if pid_is_server "${pid}" "${path}"; then
                SERVER_PIDS+=("${pid}")
                printf '%s is already running (pid %s)\n' "${name}" "${pid}"
                continue
            fi
            rm -f "$(pid_file "${name}")"
        fi

        "${PYTHON_BIN}" "${path}" \
            >"$(log_file "${name}")" 2>&1 < /dev/null &
        pid=$!
        SERVER_PIDS+=("${pid}")
        printf '%s\n' "${pid}" >"$(pid_file "${name}")"
        sleep 1
        if pid_is_server "${pid}" "${path}"; then
            printf 'Started %s (pid %s), log: %s\n' \
                "${name}" "${pid}" "$(log_file "${name}")"
        else
            rm -f "$(pid_file "${name}")"
            printf 'Failed to start %s; see %s\n' \
                "${name}" "$(log_file "${name}")" >&2
            return 1
        fi
    done

    for pid in "${SERVER_PIDS[@]}"; do
        wait "${pid}" 2>/dev/null || true
    done
}

wait_for_servers() {
    printf 'All MCP servers are running in the foreground. Press Ctrl-C to stop.\n'

    while true; do
        local pid
        for pid in "${SERVER_PIDS[@]}"; do
            if ! kill -0 "${pid}" 2>/dev/null; then
                printf 'MCP server process %s exited unexpectedly\n' "${pid}" >&2
                return 1
            fi
        done
        sleep 1
    done
}

cleanup_servers() {
    local pid
    local attempt
    local name

    (( CLEANING_UP == 1 )) && return
    CLEANING_UP=1

    for pid in "${SERVER_PIDS[@]}"; do
        if kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
        fi
    done

    for attempt in {1..10}; do
        local running=0
        for pid in "${SERVER_PIDS[@]}"; do
            if kill -0 "${pid}" 2>/dev/null; then
                running=1
            fi
        done
        (( running == 0 )) && break
        sleep 1
    done

    for name in "${SERVER_NAMES[@]}"; do
        local pid_file_path
        pid_file_path="$(pid_file "${name}")"
        if [[ -f "${pid_file_path}" ]]; then
            pid="$(<"${pid_file_path}")"
            if [[ " ${SERVER_PIDS[*]} " == *" ${pid} "* ]]; then
                if kill -0 "${pid}" 2>/dev/null; then
                    kill -KILL "${pid}" 2>/dev/null || true
                fi
                rm -f "${pid_file_path}"
                printf 'Stopped %s\n' "${name}"
            fi
        fi
    done
}

stop_servers() {
    local name
    local path
    local pid
    local attempt

    for name in "${SERVER_NAMES[@]}"; do
        path="${SCRIPT_DIR}/${name}.py"
        if [[ ! -f "$(pid_file "${name}")" ]]; then
            printf '%s is not tracked as running\n' "${name}"
            continue
        fi

        pid="$(<"$(pid_file "${name}")")"
        if ! pid_is_server "${pid}" "${path}"; then
            rm -f "$(pid_file "${name}")"
            printf 'Removed stale pid file for %s\n' "${name}"
            continue
        fi

        kill "${pid}"
        for attempt in {1..10}; do
            if ! kill -0 "${pid}" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        if kill -0 "${pid}" 2>/dev/null; then
            printf 'Server %s did not stop after SIGTERM\n' "${name}" >&2
            return 1
        fi
        rm -f "$(pid_file "${name}")"
        printf 'Stopped %s\n' "${name}"
    done
}

case "${1:-start}" in
    start)
        trap cleanup_servers EXIT
        trap 'exit 130' INT
        trap 'exit 143' TERM
        trap 'exit 129' HUP
        start_servers
        wait_for_servers
        ;;
    stop)
        stop_servers
        ;;
    restart)
        stop_servers
        trap cleanup_servers EXIT
        trap 'exit 130' INT
        trap 'exit 143' TERM
        trap 'exit 129' HUP
        start_servers
        wait_for_servers
        ;;
    *)
        printf 'Usage: %s {start|stop|restart}\n' "${0##*/}" >&2
        exit 2
        ;;
esac
