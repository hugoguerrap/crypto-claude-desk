---
name: quick
description: Quick single-agent market check. Usage: /quick BTC or /quick ETH
user-invocable: true
---

# Quick Market Check

Get a fast snapshot of $ARGUMENTS using a single agent. No team needed.

## Workflow

1. Delegate using the Task tool with `subagent_type: general-purpose` and `model: haiku`:

   "You are the market-monitor agent. Quick market snapshot for $ARGUMENTS.
   Use these MCP tools (call them in parallel):
   - get_exchange_prices(symbol='{SYMBOL}/USDT') for live price, 24h change, volume
   - get_fear_greed_index() for market sentiment
   - get_funding_rate(symbol='{SYMBOL}') for futures funding rate
   Also run a WebSearch for '{SYMBOL} crypto news today' to catch any breaking events.
   Be concise — this is a quick check, not a full analysis.
   Do NOT use the Edit tool."

2. Present the result directly to the user. Keep it brief.

## When to suggest deeper analysis
If the agent detects any of these, suggest running `/analyze $ARGUMENTS`:
- Price change >5% in 24h
- Extreme Fear or Extreme Greed
- Funding rate anomaly (>0.05% or <-0.05%)
- Volume spike >2x average
