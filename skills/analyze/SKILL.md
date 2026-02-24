---
name: analyze
description: Run a comprehensive multi-agent crypto analysis with phased execution. Usage: /analyze BTC or /analyze ETH SOL
user-invocable: true
---

# Full Crypto Analysis

Run a comprehensive analysis of $ARGUMENTS using 5 specialized agents in 3 sequential phases. Each phase writes a report file; the next phase reads those files before starting.

**All agents use `subagent_type: general-purpose`** with explicit `model` to ensure MCP tool access. Include "Do NOT use the Edit tool" in every prompt.

## Workflow

### Phase 0: Setup
1. Create directory: `data/reports/YYYY-MM-DD-{symbol}/` (use today's date)

### Phase 1: Data Gathering (3 agents in parallel)
Spawn ALL 3 agents simultaneously using the Task tool. Do NOT wait for one before spawning the next — launch all 3 in a single response.

1. **market-monitor** — Task with `subagent_type: general-purpose`, `model: haiku`:
   "You are the market-monitor agent. Read agents/market-monitor.md for your full analysis framework.
   Gather real-time market data for $ARGUMENTS.
   Use crypto-exchange MCP (get_exchange_prices, fetch_ohlcv_data, analyze_volume_patterns) for ACCURATE current prices and volume.
   Use crypto-data MCP (get_fear_greed_index, get_dominance_stats, get_global_market_stats) for market metadata.
   Use crypto-futures MCP (get_funding_rate, get_open_interest, get_long_short_ratio) for derivatives data.
   Use WebSearch for whale alerts and breaking news.
   Write your complete report to data/reports/YYYY-MM-DD-{symbol}/market-data.md.
   Do NOT use the Edit tool."

2. **technical-analyst** — Task with `subagent_type: general-purpose`, `model: sonnet`:
   "You are the technical-analyst agent. Read agents/technical-analyst.md for your full analysis framework.
   Run full technical analysis for $ARGUMENTS.
   First call get_prediction_track_record(agent='technical-analyst', symbol='{SYMBOL}/USDT') from crypto-learning-db to check your past accuracy — calibrate your analysis based on where you've been right/wrong.
   Use crypto-technical MCP (calculate_rsi, calculate_macd, calculate_bollinger_bands, detect_chart_patterns, calculate_moving_averages, get_support_resistance, generate_trading_signals).
   Use crypto-advanced-indicators MCP (calculate_ichimoku, calculate_vwap, calculate_adx, calculate_obv, detect_divergences).
   Use crypto-exchange MCP (fetch_ohlcv_data) for price data.
   Write your complete report to data/reports/YYYY-MM-DD-{symbol}/technical-analysis.md.
   Do NOT use the Edit tool."

3. **news-sentiment** — Task with `subagent_type: general-purpose`, `model: sonnet`:
   "You are the news-sentiment agent. Read agents/news-sentiment.md for your full analysis framework.
   Analyze latest news and social sentiment for $ARGUMENTS.
   First call get_prediction_track_record(agent='news-sentiment', symbol='{SYMBOL}/USDT') from crypto-learning-db to check your past accuracy.
   Use WebSearch extensively: search for '{SYMBOL} crypto news today', '{SYMBOL} twitter sentiment', '{SYMBOL} reddit discussion', regulatory news.
   Use WebFetch to read full articles when headlines are significant.
   Cover: breaking news, regulatory updates, social media mood, FUD/FOMO detection, contrarian signals.
   Write your complete report to data/reports/YYYY-MM-DD-{symbol}/news-sentiment.md.
   Do NOT use the Edit tool."

### Phase 1 Verification
After all 3 Task calls return, verify the report files exist on disk using Glob. If news-sentiment did not produce a file (timeout), proceed without it — note the gap in the Phase 2 prompt.

### Phase 2: Risk Assessment (1 agent, after Phase 1)
Only spawn AFTER Phase 1 files are confirmed on disk.

4. **risk-specialist** — Task with `subagent_type: general-purpose`, `model: sonnet`:
   "You are the risk-specialist agent. Read agents/risk-specialist.md for your full analysis framework.
   FIRST read these Phase 1 reports — they are ALREADY written on disk:
   - data/reports/YYYY-MM-DD-{symbol}/market-data.md
   - data/reports/YYYY-MM-DD-{symbol}/technical-analysis.md
   - data/reports/YYYY-MM-DD-{symbol}/news-sentiment.md (if it exists)
   Read them before doing anything else.
   Call get_prediction_track_record(agent='risk-specialist', symbol='{SYMBOL}/USDT') from crypto-learning-db to check your past accuracy.
   Use crypto-technical MCP (calculate_volatility, get_correlation_analysis).
   Use crypto-market-microstructure MCP (analyze_orderbook_depth, detect_orderbook_imbalance, calculate_spread_metrics, analyze_order_flow, detect_spoofing_patterns, calculate_market_impact).
   Use crypto-exchange MCP (get_cross_exchange_liquidity).
   Use crypto-data MCP (get_fear_greed_index, get_crypto_prices).
   Write your complete report to data/reports/YYYY-MM-DD-{symbol}/risk-assessment.md.
   Do NOT use the Edit tool."

### Phase 2 Verification
After the Task call returns, verify `risk-assessment.md` exists on disk.

### Phase 3: Trading Decision (1 agent, after Phase 2)
Only spawn AFTER risk-assessment.md is confirmed on disk.

5. **portfolio-manager** — Task with `subagent_type: general-purpose`, `model: opus`:
   "You are the portfolio-manager agent. Read agents/portfolio-manager.md for your full decision framework.
   FIRST read ALL files in data/reports/YYYY-MM-DD-{symbol}/ — these are ALREADY written by previous agents. Read market-data.md, technical-analysis.md, news-sentiment.md (if exists), and risk-assessment.md.
   Call get_prediction_track_record(symbol='{SYMBOL}/USDT') from crypto-learning-db to check how this type of setup has performed historically — read the recent evaluations for context.
   Call get_portfolio_state() from crypto-learning-db to check balances and open positions.
   Verify current price with get_exchange_prices(symbol='{SYMBOL}/USDT') from crypto-exchange MCP.
   Synthesize all agent findings. Make final EXECUTE/WAIT/REJECT decision with position sizing, entry/SL/TP, and R/R ratio.
   If EXECUTE, call record_trade() from crypto-learning-db with all required fields including the learning JSON.
   Write decision to data/reports/YYYY-MM-DD-{symbol}/decision.md.
   Do NOT use the Edit tool."

### Phase 4: Record Predictions (if EXECUTE)
If the portfolio-manager's decision was EXECUTE and a trade was opened:

Delegate using Task with `subagent_type: general-purpose`, `model: opus`:
"You are the learning-agent. Read agents/learning-agent.md for your analysis framework.
Record predictions for the latest trade just opened.
Call query_trades(status='open', limit=1) from crypto-learning-db to get the trade.
Read its key_assumptions and learning fields.
Extract each testable prediction (price direction, support/resistance holds, funding expectations, risk scenarios).
Call record_prediction() from crypto-learning-db for each prediction.
Do NOT use the Edit tool."

### Phase 5: Synthesize & Present
1. Read all output files from `data/reports/YYYY-MM-DD-{symbol}/`
2. Create consolidated report at `data/reports/YYYY-MM-DD-{symbol}/full-report.md`
3. Present the portfolio-manager's EXECUTE/WAIT/REJECT decision prominently
4. If predictions were recorded, mention how many predictions are being tracked

### Output
Present a consolidated report with:
- Market data summary (prices, volume, funding, fear/greed)
- Technical signals and key levels (entry/SL/TP)
- News & sentiment overview
- Risk assessment score
- **FINAL DECISION: EXECUTE/WAIT/REJECT** with full trade parameters
