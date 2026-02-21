---
name: quick
description: Quick single-agent market check. Usage: /quick BTC or /quick ETH
user-invocable: true
---

# Quick Market Check

Get a fast snapshot of $ARGUMENTS using a single agent. No team needed.

## Workflow

1. Delegate to `market-monitor` agent (haiku - fast and cheap):
   "Quick market snapshot for $ARGUMENTS. Get current price, 24h change, volume, Fear & Greed Index, funding rate, and any notable movements. Be concise - this is a quick check, not a full analysis."

2. Present the result directly to the user. Keep it brief.

## When to suggest deeper analysis
If market-monitor detects any of these, suggest running `/analyze $ARGUMENTS`:
- Price change >5% in 24h
- Extreme Fear or Extreme Greed
- Funding rate anomaly (>0.05% or <-0.05%)
- Volume spike >2x average
