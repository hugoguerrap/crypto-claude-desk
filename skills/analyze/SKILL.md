---
name: analyze
description: Run a comprehensive multi-agent crypto analysis using Agent Teams. Usage: /analyze BTC or /analyze ETH SOL
user-invocable: true
---

# Full Crypto Analysis (Agent Team)

Run a comprehensive analysis of $ARGUMENTS using an Agent Team with parallel execution, shared task list, and phased dependencies.

## Workflow

### Phase 0: Setup
1. Create directory: `data/reports/YYYY-MM-DD-{symbol}/`
2. Create the agent team with `TeamCreate` named `analysis-{symbol}`

### Phase 1: Create Tasks
Create all 5 tasks upfront for tracking:
- Task 1: "Gather market data for $ARGUMENTS" → market-monitor
- Task 2: "Technical analysis for $ARGUMENTS" → technical-analyst
- Task 3: "News & sentiment for $ARGUMENTS" → news-sentiment
- Task 4: "Risk assessment for $ARGUMENTS" → risk-specialist (blockedBy: [1, 2, 3])
- Task 5: "Trading decision for $ARGUMENTS" → portfolio-manager (blockedBy: [4])

### Phase 2: Spawn Phase 1 Agents (parallel)
Spawn ONLY the 3 Phase 1 agents. Do NOT spawn risk-specialist or portfolio-manager yet.

1. **market-monitor** (haiku): "You are on team analysis-{symbol}. Your task is Task #1. Mark it in_progress, then gather real-time market data for $ARGUMENTS. Use crypto-exchange MCP (get_exchange_prices, get_all_tickers) for ACCURATE current prices. Use crypto-data MCP for market metadata (fear/greed, dominance, global stats, categories). Use crypto-futures MCP for funding rates, OI, long/short ratios. Use WebSearch for whale alerts and breaking news. Write your complete report to `data/reports/YYYY-MM-DD-{symbol}/market-data.md`. Mark Task #1 completed when done."

2. **technical-analyst** (sonnet): "You are on team analysis-{symbol}. Your task is Task #2. Mark it in_progress, then run full technical analysis for $ARGUMENTS. Use crypto-technical, crypto-advanced-indicators, crypto-exchange MCPs. Calculate RSI, MACD, Bollinger, moving averages, Ichimoku, VWAP. Detect patterns, support/resistance, generate trading signal. Write your complete report to `data/reports/YYYY-MM-DD-{symbol}/technical-analysis.md`. Mark Task #2 completed when done."

3. **news-sentiment** (sonnet): "You are on team analysis-{symbol}. Your task is Task #3. Mark it in_progress, then analyze latest news and social sentiment for $ARGUMENTS. Use WebSearch + WebFetch (you have NO MCP tools). Cover breaking news, regulatory updates, social media mood, FUD/FOMO detection, contrarian signals. Write your complete report to `data/reports/YYYY-MM-DD-{symbol}/news-sentiment.md`. Mark Task #3 completed when done."

### Phase 3: Wait for Phase 1 Completion
Monitor Phase 1 via TaskList. Wait until Tasks 1, 2, 3 are all `completed`.

**Timeout rule:** If after 4 minutes any Phase 1 task is still in_progress, check if the report file exists on disk using Glob. If the file exists, mark the task completed and proceed. If news-sentiment has not completed after 5 minutes, proceed to Phase 4 without it — add a note "(news-sentiment timeout — proceeding without sentiment data)" to the risk-specialist prompt.

### Phase 4: Spawn Phase 2 Agent (risk-specialist)
Only spawn AFTER Phase 1 is confirmed complete (or timed out with files on disk).

4. **risk-specialist** (sonnet): "You are on team analysis-{symbol}. Your task is Task #4. Mark it in_progress. FIRST read these Phase 1 reports: `data/reports/YYYY-MM-DD-{symbol}/market-data.md`, `technical-analysis.md`, and `news-sentiment.md` (if it exists). These files are ALREADY written — read them before doing anything else. Then calculate VaR, volatility, correlation, microstructure risk, and institutional flow detection for $ARGUMENTS. Write your complete report to `data/reports/YYYY-MM-DD-{symbol}/risk-assessment.md`. Mark Task #4 completed when done."

Wait for Task 4 to be `completed` before proceeding.

### Phase 5: Spawn Phase 3 Agent (portfolio-manager)
Only spawn AFTER risk-specialist is confirmed complete.

5. **portfolio-manager** (opus): "You are on team analysis-{symbol}. Your task is Task #5. Mark it in_progress. FIRST read ALL files in `data/reports/YYYY-MM-DD-{symbol}/` — these are ALREADY written by previous agents. Read market-data.md, technical-analysis.md, news-sentiment.md (if exists), and risk-assessment.md. ALSO read `data/trades/agent-scorecards.json` — use each agent's `confidence_adjustment` score to weight their signals (e.g., if technical-analyst has confidence_adjustment 1.3, give extra weight to their signals; if risk-specialist has 0.7, discount theirs). Then synthesize all agent findings. Make final EXECUTE/WAIT/REJECT decision with position sizing, entry/SL/TP, and R/R ratio. Write decision to `data/reports/YYYY-MM-DD-{symbol}/decision.md`. Mark Task #5 completed when done."

Wait for Task 5 to be `completed`.

### Phase 6: Record Predictions (if EXECUTE)
If the portfolio-manager's decision was EXECUTE and a trade was opened:
1. Delegate to `learning-agent`: "Record predictions for the latest trade just opened in data/trades/portfolio.json. Read the trade's agent_signals and learning fields. Extract each testable prediction (price direction, support/resistance holds, funding expectations, risk scenarios). Write prediction entries to data/trades/predictions.json following your Mission 3 instructions."

### Phase 7: Synthesize & Present
1. Read all output files from `data/reports/YYYY-MM-DD-{symbol}/`
2. Create consolidated report at `data/reports/YYYY-MM-DD-{symbol}/full-report.md`
3. Present the portfolio-manager's EXECUTE/WAIT/REJECT decision prominently
4. If predictions were recorded, mention how many predictions are being tracked
5. Shut down ALL teammates with shutdown_request
6. Clean up with TeamDelete

### Output
Present a consolidated report with:
- Market data summary (prices, volume, funding, fear/greed)
- Technical signals and key levels (entry/SL/TP)
- News & sentiment overview
- Risk assessment score
- **FINAL DECISION: EXECUTE/WAIT/REJECT** with full trade parameters
