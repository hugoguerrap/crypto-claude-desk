#!/usr/bin/env bash
# Lightweight session startup hook.
# Creates data directories if they don't exist. No heavy operations.
# Dependencies are handled by `uv run` (auto-installs on first MCP call).

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

mkdir -p "$ROOT/data/trades" \
         "$ROOT/data/reports" \
         "$ROOT/data/logs" \
         "$ROOT/.claude/agent-memory/portfolio-manager"

if [ ! -f "$ROOT/data/trades/portfolio.json" ] && [ -f "$ROOT/data/trades/portfolio.json.example" ]; then
    cp "$ROOT/data/trades/portfolio.json.example" "$ROOT/data/trades/portfolio.json"
fi
