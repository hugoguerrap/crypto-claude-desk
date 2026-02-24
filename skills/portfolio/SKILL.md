---
name: portfolio
description: View current portfolio status, open trades, and performance stats. Usage: /portfolio
user-invocable: true
---

# Portfolio Status

Show current portfolio state and performance.

## Workflow

1. Delegate using the Task tool with `subagent_type: general-purpose` and `model: opus`:

   "You are the portfolio-manager agent. Read agents/portfolio-manager.md for your full analysis framework.
   Call get_portfolio_state() from crypto-learning-db MCP to get balances and open trades.
   Call get_trade_stats() for closed trade summary.
   For each open trade, verify current price using get_exchange_prices(symbol=...) from crypto-exchange MCP.
   Present a clear portfolio status report showing:
   - Spot and futures balances (current vs initial $10,000 each)
   - All open trades with current P&L
   - Summary of closed trades (wins/losses/total PnL)
   - Overall portfolio performance percentage
   - Risk exposure: how much of portfolio is currently allocated
   - Any trades approaching stop-loss or take-profit levels
   Do NOT make any changes or decisions — this is a read-only status check.
   Do NOT use the Edit tool."

2. Present the result. If any open trades are near SL/TP levels, highlight them.
