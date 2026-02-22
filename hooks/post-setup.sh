#!/usr/bin/env bash
# Lightweight session startup hook.
# Only creates data directories. No dependency management.
# Dependencies are handled by /setup skill (first time) and uv run (ongoing).

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

mkdir -p "$ROOT/data/trades" \
         "$ROOT/data/reports" \
         "$ROOT/data/logs" \
         "$ROOT/.claude/agent-memory/portfolio-manager" 2>/dev/null || true

if [ ! -f "$ROOT/data/trades/portfolio.json" ] && [ -f "$ROOT/data/trades/portfolio.json.example" ]; then
    cp "$ROOT/data/trades/portfolio.json.example" "$ROOT/data/trades/portfolio.json"
fi
