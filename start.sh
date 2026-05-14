#!/usr/bin/env bash
# PKS Service Startup Script
# Usage:
#   ./start.sh          Start both Web UI and MCP Server
#   ./start.sh web      Start Web UI only
#   ./start.sh mcp      Start MCP Server only

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv/bin"

if [ ! -f "$VENV/pks" ]; then
    echo "Error: PKS not installed. Run: python3 -m pip install -e '.[web,mcp]'"
    exit 1
fi

start_web() {
    echo "Starting PKS Web UI at http://localhost:8420"
    "$VENV/pks" serve "$@"
}

start_mcp() {
    echo "Starting PKS MCP Server (stdio)"
    "$VENV/pks" mcp start "$@"
}

case "${1:-all}" in
    web)
        shift 2>/dev/null || true
        start_web "$@"
        ;;
    mcp)
        shift 2>/dev/null || true
        start_mcp "$@"
        ;;
    all)
        echo "Starting PKS Web UI (background) + MCP Server (foreground)"
        "$VENV/pks" serve &
        WEB_PID=$!
        echo "Web UI PID: $WEB_PID (http://localhost:8420)"
        trap "kill $WEB_PID 2>/dev/null" EXIT
        "$VENV/pks" mcp start
        ;;
    *)
        echo "Usage: $0 [web|mcp|all]"
        exit 1
        ;;
esac
