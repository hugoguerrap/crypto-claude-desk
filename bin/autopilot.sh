#!/usr/bin/env bash
# autopilot.sh — Run crypto trading desk workflows headless via cron.
#
# Skills are NOT invoked via slash commands in -p mode. This script maps
# workflow names to detailed natural language prompts that Claude can
# execute using CLAUDE.md routing + MCP tools.
#
# Works in both modes:
#   - Installed plugin:  agents/MCP/skills auto-discovered, no extra flags.
#   - Local development: auto-detects and passes --plugin-dir so Claude Code
#     discovers agents/, mcp-servers/, and skills/.
#
# Usage:
#   ./bin/autopilot.sh monitor
#   ./bin/autopilot.sh quick "BTC ETH SOL"
#   ./bin/autopilot.sh analyze "BTC"
#   ./bin/autopilot.sh portfolio
#
# Crontab examples:
#   0 * * * *   /path/to/crypto-trading-desk/bin/autopilot.sh monitor
#   0 8 * * *   /path/to/crypto-trading-desk/bin/autopilot.sh quick "BTC ETH SOL"
#   0 9 * * 1   /path/to/crypto-trading-desk/bin/autopilot.sh analyze "BTC"
#   0 16 * * 1-5 /path/to/crypto-trading-desk/bin/autopilot.sh portfolio

set -euo pipefail

# ---------------------------------------------------------------------------
# Project root (relative to this script)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# ---------------------------------------------------------------------------
# PATH — cron doesn't inherit your shell's PATH
# ---------------------------------------------------------------------------
export PATH="$HOME/.local/bin:$HOME/.claude/local:/usr/local/bin:/usr/bin:/bin:$PATH"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR="$PROJECT_DIR/data/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).log"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

# ---------------------------------------------------------------------------
# Allowed tools — pre-approve so cron doesn't hang on permission prompts
# ---------------------------------------------------------------------------
ALLOWED_TOOLS="Read,Write,Grep,Glob,WebSearch,WebFetch,mcp__crypto-data,mcp__crypto-exchange,mcp__crypto-technical,mcp__crypto-futures,mcp__crypto-advanced-indicators,mcp__crypto-market-microstructure,mcp__crypto-learning-db"

# ---------------------------------------------------------------------------
# Plugin discovery — detect if running as local dev (not an installed plugin)
# ---------------------------------------------------------------------------
# When installed via `claude plugin install`, Claude Code discovers agents,
# MCP servers, and skills automatically. For local clones / forks, we need
# --plugin-dir so Claude Code loads everything from this directory.
#
# Detection: if plugin.json exists, this is a plugin repo (local or installed).
# We always pass --plugin-dir for safety — it's a no-op if already installed.
PLUGIN_FLAGS=""
if [ -f "$PROJECT_DIR/plugin.json" ] || [ -d "$PROJECT_DIR/agents" ]; then
    PLUGIN_FLAGS="--plugin-dir $PROJECT_DIR"
fi

# ---------------------------------------------------------------------------
# Workflow → Prompt mapping
# ---------------------------------------------------------------------------
WORKFLOW="${1:-}"
ARGS="${2:-}"

case "$WORKFLOW" in
  monitor)
    PROMPT="Run the autonomous monitoring loop for my crypto portfolio. Follow these steps:
1. Call get_portfolio_state() from crypto-learning-db to check open trades.
2. If there are open trades, delegate to market-monitor agent to get current prices for each symbol using crypto-exchange MCP.
3. Compare prices against each trade's stop_loss and take_profit. For longs: SL hit if price <= stop_loss, TP hit if price >= take_profit. For shorts: opposite.
4. If any SL or TP was hit, delegate to portfolio-manager agent to close those trades using close_trade() from crypto-learning-db.
5. For profitable trades NOT closed, delegate to risk-specialist agent to evaluate trailing stop adjustment using update_trade().
6. For any trades closed, delegate to learning-agent to run post-mortem: query_predictions for the trade, validate each prediction with NL evaluation, upsert_pattern if a setup is identified.
7. Delegate to learning-agent to call find_expired_predictions() with current prices and validate any expired predictions.
8. If today is near month end, delegate to learning-agent to call generate_summary(summary_type='monthly').
9. Write a brief monitor report summarizing what happened."
    ;;

  quick)
    if [ -z "$ARGS" ]; then
      echo "Usage: $0 quick \"BTC ETH SOL\"" >&2
      exit 1
    fi
    PROMPT="Quick market snapshot for ${ARGS}. Delegate to market-monitor agent: get current price, 24h change, volume, Fear & Greed Index, funding rate, and any notable movements for ${ARGS}. Be concise."
    ;;

  analyze)
    if [ -z "$ARGS" ]; then
      echo "Usage: $0 analyze \"BTC\"" >&2
      exit 1
    fi
    PROMPT="Run a full 5-agent analysis for ${ARGS}. Follow the /analyze workflow:
Phase 1 - Spawn 3 agents IN PARALLEL using the Task tool:
  1. market-monitor: gather prices, volume, funding, fear/greed for ${ARGS}. Write to data/reports/$(date +%Y-%m-%d)-${ARGS}/market-data.md
  2. technical-analyst: RSI, MACD, Bollinger, patterns, signals for ${ARGS}. Write to data/reports/$(date +%Y-%m-%d)-${ARGS}/technical-analysis.md
  3. news-sentiment: latest news and social sentiment for ${ARGS}. Write to data/reports/$(date +%Y-%m-%d)-${ARGS}/news-sentiment.md
Wait for all 3 to finish. Verify files exist on disk.
Phase 2 - Spawn risk-specialist: read Phase 1 files, calculate VaR, volatility, microstructure risk. Write to data/reports/$(date +%Y-%m-%d)-${ARGS}/risk-assessment.md
Wait for it to finish.
Phase 3 - Spawn portfolio-manager: read ALL report files, check prediction track record via get_prediction_track_record(), check portfolio state, make EXECUTE/WAIT/REJECT decision. Write to data/reports/$(date +%Y-%m-%d)-${ARGS}/decision.md
If EXECUTE, delegate to learning-agent to record predictions.
Create consolidated full-report.md and present the decision."
    ;;

  portfolio)
    PROMPT="Check my crypto portfolio status. Delegate to portfolio-manager agent: call get_portfolio_state() from crypto-learning-db, show current balances (spot and futures), list all open trades with current P&L, and summarize overall performance."
    ;;

  *)
    echo "Crypto Trading Desk — Autopilot" >&2
    echo "" >&2
    echo "Usage: $0 <workflow> [args]" >&2
    echo "" >&2
    echo "Workflows:" >&2
    echo "  monitor              Check SL/TP, close trades, evaluate predictions" >&2
    echo "  quick \"BTC ETH\"      Fast market snapshot" >&2
    echo "  analyze \"BTC\"        Full 5-agent analysis with decision" >&2
    echo "  portfolio            Portfolio status and open trades" >&2
    echo "" >&2
    echo "Crontab examples:" >&2
    echo "  0 * * * *   $0 monitor" >&2
    echo "  0 8 * * *   $0 quick \"BTC ETH SOL\"" >&2
    echo "  0 9 * * 1   $0 analyze \"BTC\"" >&2
    echo "  0 16 * * 1-5 $0 portfolio" >&2
    echo "" >&2
    echo "Custom workflows:" >&2
    echo "  Add a new case block in the WORKFLOW section of this script." >&2
    echo "  Each workflow is a natural language prompt — describe what you" >&2
    echo "  want Claude to do using the agents and MCP tools available." >&2
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
echo "[$TIMESTAMP] Running: $WORKFLOW ${ARGS:-}" >> "$LOG_FILE"

# shellcheck disable=SC2086
claude -p "$PROMPT" \
    --allowedTools "$ALLOWED_TOOLS" \
    $PLUGIN_FLAGS \
    --output-format text \
    >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

TIMESTAMP_END="$(date '+%Y-%m-%d %H:%M:%S')"
echo "[$TIMESTAMP_END] Finished $WORKFLOW (exit: $EXIT_CODE)" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"

exit $EXIT_CODE
