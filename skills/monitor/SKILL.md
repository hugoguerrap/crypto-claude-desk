---
name: monitor
description: Autonomous monitoring loop. Checks open trades against SL/TP levels, closes trades that hit targets, evaluates expired predictions, and generates periodic summaries. Run via cron for full autonomy. Usage: /monitor
user-invocable: true
---

# Monitor - Autonomous Learning Loop

Closes the autonomous loop: check trades, close hits, evaluate predictions, generate summaries.

**All agents use `subagent_type: general-purpose`** with explicit `model` to ensure MCP tool access. Include "Do NOT use the Edit tool" in every prompt.

## Workflow

### Step 1: Get Current Prices
Delegate using Task with `subagent_type: general-purpose`, `model: haiku`:

"You are the market-monitor agent. Get current prices for ALL symbols that have open trades.
Call get_portfolio_state() from crypto-learning-db first to see which symbols have open positions.
Then use get_exchange_prices(symbol=...) from crypto-exchange MCP to get live prices for each symbol.
Return a JSON object like: {\"BTC/USDT\": 98500, \"ETH/USDT\": 3200}
Do NOT use the Edit tool."

### Step 2: Check Open Trades Against SL/TP
Using the prices from Step 1 and the open trades from get_portfolio_state():

For each open trade, check:
- **Long trade**: Did price drop to or below `stop_loss`? Did price rise to or above `take_profit`?
- **Short trade**: Did price rise to or above `stop_loss`? Did price drop to or below `take_profit`?

If SL or TP was hit, delegate using Task with `subagent_type: general-purpose`, `model: opus`:

"You are the portfolio-manager agent. Close trade {trade_id}. Current price is ${price}. The {SL/TP} at ${level} was hit.
Call close_trade(trade_id='{trade_id}', exit_price={price}, close_reason='{SL/TP} hit at ${level}') from crypto-learning-db.
Do NOT use the Edit tool."

### Step 2b: Trailing Stop Adjustment
For open trades that were NOT closed (still active), check if the trade is profitable:
- **Long**: current price > entry_price
- **Short**: current price < entry_price

If profitable AND the current stop_loss hasn't been optimally trailed, delegate using Task with `subagent_type: general-purpose`, `model: sonnet`:

"You are the risk-specialist agent. Read agents/risk-specialist.md for context.
Trade {trade_id} ({symbol}, {side}) is profitable. Entry: ${entry}, Current: ${price}, SL: ${stop_loss}, TP: ${take_profit}.
Analyze whether to trail the stop-loss. Use calculate_volatility(symbol=...) and get_support_resistance(symbol=...) from crypto-technical MCP.
If you recommend adjusting, call update_trade(trade_id='{trade_id}', stop_loss={new_sl}, notes='your reasoning') from crypto-learning-db.
Rules: only trail in profitable direction, never widen the stop, leave room for normal volatility.
Do NOT use the Edit tool."

### Step 3: Post-Mortem for Closed Trades
For each trade closed in Step 2, delegate using Task with `subagent_type: general-purpose`, `model: opus`:

"You are the learning-agent. Read agents/learning-agent.md for your analysis framework.
Trade {trade_id} was just closed ({result}, PnL: {pnl}). Do a full post-mortem:
1. Call query_predictions(trade_id='{trade_id}') from crypto-learning-db to find all predictions
2. For each pending prediction, evaluate: read the original, compare to what happened, write a detailed NL evaluation
3. Call validate_prediction() with your evaluation for each one
4. Call upsert_pattern() if you identify a named pattern
5. Write a post-mortem report to data/reports/
Do NOT use the Edit tool."

### Step 4: Evaluate Expired Predictions
Delegate using Task with `subagent_type: general-purpose`, `model: opus`:

"You are the learning-agent. Call find_expired_predictions(current_prices='{prices_json}') from crypto-learning-db using the current prices.
For each expired prediction:
1. Read the original prediction text
2. Compare to the current price / market state
3. Write a natural language evaluation explaining how close it was and why
4. Call validate_prediction() with your evaluation
Do NOT use the Edit tool."

### Step 5: Monthly Summary (conditional)
Check if today is the last day of the month (or within 2 days of month end).
If yes, delegate using Task with `subagent_type: general-purpose`, `model: opus`:

"You are the learning-agent. Generate a monthly summary.
Call generate_summary(summary_type='monthly') from crypto-learning-db.
Also check if it's end of quarter — if so, call generate_summary(summary_type='quarterly') too.
Do NOT use the Edit tool."

### Step 6: Report
Present a summary of what happened:
```
## Monitor Report

**Open Trades:** X active
**Trades Closed This Run:** X (list with PnL)
**Predictions Evaluated:** X expired validated
**Summary Generated:** Yes/No

### Next Actions
- [Any trades approaching SL/TP levels]
- [Any concerning patterns noticed]
```
