---
name: close-trade
description: Close an open trade and run post-mortem analysis. Usage: /close-trade trade_001 or /close-trade trade_001 at 98500
user-invocable: true
---

# Close Trade & Post-Mortem

Close trade $ARGUMENTS and run a post-mortem analysis.

## Workflow

### Step 1: Close the Trade
Delegate using the Task tool with `subagent_type: general-purpose` and `model: opus`:

"You are the portfolio-manager agent. Read agents/portfolio-manager.md for your decision framework.
Close trade $ARGUMENTS. If a price is specified after 'at', use that as exit price. Otherwise, get the current market price using get_exchange_prices() from crypto-exchange MCP.
Call close_trade(trade_id='...', exit_price=..., close_reason='...') from crypto-learning-db MCP. PnL, portfolio balance, and stats are updated automatically.
Do NOT use the Edit tool."

### Step 2: Post-Mortem Analysis
After the trade is closed, delegate using the Task tool with `subagent_type: general-purpose` and `model: opus`:

"You are the learning-agent. Read agents/learning-agent.md for your analysis framework.
Run a post-mortem analysis on the recently closed trade $ARGUMENTS.
Call query_trades(status='closed', limit=1) from crypto-learning-db to get the trade data.
Read any related reports from data/reports/.
Analyze what worked, what didn't, and provide specific recommendations for improvement.
Do NOT use the Edit tool."

### Step 3: Validate Predictions & Update Patterns
After the post-mortem, delegate using the Task tool with `subagent_type: general-purpose` and `model: opus`:

"You are the learning-agent. Validate all predictions for trade $ARGUMENTS.
Call query_predictions(trade_id='...') from crypto-learning-db to find all predictions tied to this trade.
Compare each prediction against the actual outcome.
Call validate_prediction() for each one with a detailed NL evaluation of how close the prediction was and what we can learn.
Then call upsert_pattern() to update the pattern library with the setup from this trade.
Do NOT use the Edit tool."

### Step 4: Present Results
Show:
1. Trade closure summary (entry, exit, PnL)
2. Post-mortem analysis
3. Prediction accuracy (how many correct vs incorrect, with evaluations)
4. Pattern identified (win rate, recommendation)
5. Lessons learned
