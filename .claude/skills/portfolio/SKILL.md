---
name: portfolio
description: View current portfolio status, open trades, and performance stats. Usage: /portfolio
user-invocable: true
---

# Portfolio Status

Show current portfolio state and performance.

## Workflow

1. Delegate to `portfolio-manager` agent:
   "Read data/trades/portfolio.json and present a clear portfolio status report. Show:
   - Spot and futures balances (current vs initial)
   - All open trades with current P&L (verify current prices via crypto-data MCP)
   - Summary of closed trades (wins/losses/total PnL)
   - Overall portfolio performance percentage
   - Risk exposure: how much of portfolio is currently allocated
   - Any trades approaching stop-loss or take-profit levels
   Do NOT make any changes or decisions - this is a read-only status check."

2. Present the result. If any open trades are near SL/TP levels, highlight them.
