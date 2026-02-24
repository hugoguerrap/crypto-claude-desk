---
name: validate-predictions
description: Review and validate pending predictions against current market data. Usage: /validate-predictions
user-invocable: true
---

# Validate Predictions

Review all pending predictions and check them against current market data.

## Workflow

### Step 0: Auto-Find Expired Predictions
Delegate using the Task tool with `subagent_type: general-purpose` and `model: opus`:

"You are the learning-agent. Read agents/learning-agent.md for your analysis framework.
First, use get_crypto_prices() from crypto-data MCP to get current prices for major coins (bitcoin, ethereum, solana, etc.).
Then call find_expired_predictions(current_prices='{\"BTC/USDT\": ..., \"ETH/USDT\": ...}') from crypto-learning-db to discover predictions whose timeframe has passed.
For each expired prediction, reason about how close it was and validate with an NL evaluation using validate_prediction().
Do NOT use the Edit tool."

### Step 1: Check Remaining Pending Predictions
Delegate using the Task tool with `subagent_type: general-purpose` and `model: opus`:

"You are the learning-agent. Call query_predictions(status='pending') from crypto-learning-db for predictions still within their timeframe.
For each prediction:
1. Use get_exchange_prices(symbol=...) from crypto-exchange MCP to check current price
2. Compare current price against the prediction's target_value
3. Report current progress toward or away from target
Do NOT use the Edit tool."

### Step 2: Present Results
Show a summary table:

```
## Prediction Validation Report

### Resolved This Check
| ID | Agent | Prediction | Target | Actual | Result |
|----|-------|-----------|--------|--------|--------|

### Still Pending
| ID | Agent | Prediction | Target | Current | Progress | Expires |
|----|-------|-----------|--------|---------|----------|---------|

### Overall Accuracy
- Total predictions: X
- Correct: X (X%)
- Incorrect: X (X%)
- Pending: X

### Track Record by Setup Type
| Setup Type | Total | Correct | Accuracy | Trend |
|-----------|-------|---------|----------|-------|
```
