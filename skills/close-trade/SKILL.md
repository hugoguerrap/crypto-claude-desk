---
name: close-trade
description: Close an open trade and run post-mortem analysis. Usage: /close-trade trade_001 or /close-trade trade_001 at 98500
user-invocable: true
---

# Close Trade & Post-Mortem

Close trade $ARGUMENTS and run a post-mortem analysis.

## Workflow

### Step 1: Close the Trade
Delegate to `portfolio-manager` agent:
"Close trade $ARGUMENTS. If a price is specified, use that as exit price. Otherwise, use the current market price from crypto-data MCP. Move the trade from open_trades to closed_trades, calculate PnL, update portfolio balance and stats."

### Step 2: Post-Mortem Analysis
After the trade is closed, delegate to `learning-agent` agent:
"Run a post-mortem analysis on the recently closed trade $ARGUMENTS. Read the trade data from data/trades/portfolio.json and any related reports from data/reports/. Analyze what worked, what didn't, grade each agent's signals, identify patterns, and provide specific recommendations for improvement."

### Step 3: Validate Predictions & Update Scorecards
After the post-mortem, delegate to `learning-agent` agent:
"Validate all predictions for trade $ARGUMENTS. Read data/trades/predictions.json and find all predictions tied to this trade_id. Compare each prediction against the actual outcome from the closed trade. Mark predictions as correct/incorrect/expired. Update data/trades/agent-scorecards.json with accuracy scores and confidence adjustments. Update data/trades/patterns.json with the pattern from this trade (add new or update existing). Write all three files."

### Step 4: Present Results
Show:
1. Trade closure summary (entry, exit, PnL)
2. Post-mortem analysis
3. Prediction accuracy (how many correct vs incorrect)
4. Agent scorecard updates (who improved, who declined)
5. Pattern identified (win rate, recommendation)
6. Lessons learned
