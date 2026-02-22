---
name: validate-predictions
description: Review and validate pending predictions against current market data. Usage: /validate-predictions
user-invocable: true
---

# Validate Predictions

Review all pending predictions and check them against current market data.

## Workflow

### Step 1: Check Pending Predictions
Delegate to `learning-agent` agent:
"Read data/trades/predictions.json and find all predictions with status 'pending'. For each pending prediction:
1. Use crypto-data MCP to check current price of the symbol
2. Compare current price against the prediction's target_value
3. Check if the prediction's timeframe_hours has expired
4. If expired: mark as 'correct' or 'incorrect' based on whether the prediction came true, fill actual_outcome
5. If still within timeframe: report current progress toward or away from target
6. Update data/trades/predictions.json with any status changes
7. If any predictions were resolved, also update data/trades/agent-scorecards.json with accuracy scores"

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

### Agent Accuracy Rankings
| Agent | Accuracy | Confidence Adj. | Streak |
|-------|----------|-----------------|--------|
```
