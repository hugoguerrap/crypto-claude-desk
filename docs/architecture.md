# Architecture

Technical deep-dive into the Crypto Trading Desk multi-agent system.

---

## Routing Logic

The coordinator (Claude Code main conversation) reads `CLAUDE.md` and classifies every user query into one of four routing paths.

### 1. Quick Query (single subagent)

Used for simple data points: a price check, a single indicator, a news summary. One agent is dispatched via the Task tool.

| Query Pattern | Agent | Model |
|---|---|---|
| Price, volume, market overview | market-monitor | haiku |
| RSI, MACD, indicators, chart patterns | technical-analyst | sonnet |
| News, sentiment, FUD/FOMO | news-sentiment | sonnet |
| Portfolio status, trade history | portfolio-manager | opus |
| Pattern lookup, pre-trade confidence | learning-agent | haiku |

**Latency:** ~10-20 seconds.

### 2. Standard Analysis (2-3 parallel subagents)

Used for "analyze X" requests that do not explicitly ask for a full analysis or recommendation. The coordinator launches 2-3 agents in parallel via the Task tool, then synthesizes results.

Typical combination: market-monitor + technical-analyst + news-sentiment.

**Latency:** ~30-60 seconds.

### 3. Full Analysis with Decision (5-agent Agent Team)

Used for `/analyze`, "full analysis", "should I buy", or any request asking for a recommendation. This creates an Agent Team with 5 teammates and enforces sequential phase dependencies.

**Latency:** ~3-5 minutes.

### 4. Special Queries (targeted single agent)

- "Close trade X" --> portfolio-manager (close) + learning-agent (post-mortem)
- "What patterns have we seen?" --> learning-agent
- "Risk on my position?" --> risk-specialist

---

## DAG Dependency Model (Full Analysis)

The full analysis follows a strict three-phase DAG where later phases depend on earlier phases having written their report files to disk.

```
Phase 1 (parallel - spawn simultaneously)
+------------------------------------------+
| market-monitor  --> market-data.md       |
| technical-analyst --> technical-analysis.md |
| news-sentiment  --> news-sentiment.md    |
+------------------------------------------+
          |
          | Wait: all 3 files exist on disk
          | (5-minute timeout for news-sentiment)
          v
Phase 2 (sequential - spawn after Phase 1)
+------------------------------------------+
| risk-specialist                          |
|   reads: market-data.md                  |
|          technical-analysis.md           |
|          news-sentiment.md               |
|   writes: risk-assessment.md             |
+------------------------------------------+
          |
          | Wait: risk-assessment.md exists
          v
Phase 3 (sequential - spawn after Phase 2)
+------------------------------------------+
| portfolio-manager                        |
|   reads: ALL Phase 1 + Phase 2 files     |
|   writes: decision.md                    |
+------------------------------------------+
          |
          v
Coordinator reads all files, creates full-report.md,
presents EXECUTE / WAIT / REJECT decision to user.
```

**Key rules:**

- Phase 2 and Phase 3 agents are NOT spawned until the previous phase is confirmed complete.
- Completion is verified by checking TaskList status AND confirming report files exist on disk.
- If news-sentiment has not completed after 5 minutes, the coordinator proceeds without it and notes the gap in the risk-specialist prompt.
- All reports are written to `data/reports/YYYY-MM-DD-{symbol}/`.

---

## File-Based Coordination

Agents do not pass messages to each other. Instead, they write structured Markdown reports to a shared directory. Later-phase agents read those files before beginning their own analysis.

```
data/reports/2026-02-20-BTC/
    market-data.md          <-- market-monitor output
    technical-analysis.md   <-- technical-analyst output
    news-sentiment.md       <-- news-sentiment output
    risk-assessment.md      <-- risk-specialist output (reads above 3)
    decision.md             <-- portfolio-manager output (reads all 4)
    full-report.md          <-- coordinator synthesis (reads all 5)
```

This approach was chosen over message passing because:

1. It is inspectable -- you can read every agent's raw output on disk.
2. It is resilient -- if an agent fails, its missing file is detectable.
3. It requires no custom code -- Claude Code's Read/Write tools handle everything.

---

## Model Optimization Strategy

Each agent runs on the cheapest model that can reliably handle its task.

| Tier | Model | Agents | Rationale |
|---|---|---|---|
| Scout | haiku | market-monitor, learning-agent | Data gathering and pattern lookup require speed, not deep reasoning. |
| Analyst | sonnet | technical-analyst, news-sentiment, risk-specialist | Analysis requires multi-step reasoning and synthesis. |
| Decision Maker | opus | portfolio-manager, system-builder | Final trading decisions and code generation require the highest judgment quality. |

This tiered approach saves approximately 40-60% in token costs compared to running all agents on sonnet or opus, with no measurable decrease in analysis quality.

---

## Agent Configuration

Each agent is defined by a Markdown file in `agents/` with YAML frontmatter.

### Frontmatter Fields

```yaml
---
name: technical-analyst            # Agent identifier
description: "..."                 # When to use this agent
model: sonnet                      # haiku | sonnet | opus
mcpServers:                        # MCP servers this agent can access
  - crypto-technical
  - crypto-advanced-indicators
  - crypto-exchange
  - crypto-data
tools: WebSearch, Read, Write      # Native Claude Code tools allowed
disallowedTools: Edit              # Tools explicitly blocked
maxTurns: 12                       # Maximum conversation turns
memory: project                    # (optional) Persistent memory scope
---
```

### Principle of Least Privilege

Each agent is restricted to only the tools and MCP servers it needs:

| Agent | Allowed MCPs | Allowed Tools | Blocked Tools |
|---|---|---|---|
| market-monitor | data, futures, exchange | WebSearch, Read, Write | Edit |
| technical-analyst | technical, advanced-indicators, exchange, data | WebSearch, Read, Write | Edit |
| news-sentiment | (none) | WebSearch, WebFetch, Read, Write | Edit |
| risk-specialist | technical, microstructure, data, exchange | WebSearch, Read, Write | Edit |
| portfolio-manager | data | Read, Grep, Write | -- |
| learning-agent | data | Read, Grep, Write | Edit, Bash, WebSearch, WebFetch |
| system-builder | (none) | Read, Write, Grep, Glob, WebSearch, WebFetch | Edit, Bash |

### Persistent Memory

Two agents use `memory: project` to accumulate knowledge across sessions:

- **portfolio-manager**: Remembers past decisions, win rates, and portfolio rules.
- **learning-agent**: Builds a pattern library with named setups, historical accuracy, and agent confidence scores.

---

## MCP Server Details

All 6 MCP servers are Python files using FastMCP. They require no API keys -- all data comes from public exchange APIs via CCXT or CoinGecko.

### crypto-data (11 tools)

Source: CoinGecko API. Used for market metadata, NOT live prices (CoinGecko can be minutes stale).

| Tool | Description |
|---|---|
| `get_bitcoin_price` | Current BTC price |
| `get_crypto_prices` | Prices for multiple coins |
| `get_coin_details` | Detailed coin info (market cap, supply, ATH) |
| `get_market_rankings` | Market cap rankings |
| `get_price_history` | Historical price data |
| `get_market_trends` | Global market trends and trending coins |
| `compare_crypto_performance` | Multi-coin performance comparison |
| `get_global_market_stats` | Total market cap, volume, dominance |
| `get_fear_greed_index` | Fear & Greed Index (current + 7-day average) |
| `get_dominance_stats` | BTC/ETH market dominance |
| `get_crypto_categories` | Category breakdown (DeFi, L1, Meme, etc.) |

### crypto-exchange (16 tools)

Source: CCXT multi-exchange (Binance, Kraken, Bitfinex, KuCoin, MEXC). Primary source for accurate live prices.

| Tool | Description |
|---|---|
| `get_exchange_prices` | Live prices from multiple exchanges |
| `get_arbitrage_opportunities` | Cross-exchange price discrepancies |
| `get_orderbook_data` | Order book with liquidity analysis |
| `get_exchange_volume` | 24h volume comparison across exchanges |
| `get_trading_pairs` | Available trading pairs per exchange |
| `compare_exchange_prices` | Price comparison with arbitrage detection |
| `get_exchange_status` | Exchange operational status |
| `fetch_ohlcv_data` | OHLCV candlestick data |
| `fetch_multiple_timeframes` | Multi-timeframe OHLCV analysis |
| `fetch_recent_trades` | Recent trades with sentiment analysis |
| `get_exchange_markets_info` | Exchange market statistics |
| `get_all_tickers` | All tickers filtered by quote currency |
| `analyze_volume_patterns` | Volume anomaly detection |
| `get_cross_exchange_liquidity` | Cross-exchange liquidity analysis |
| `get_market_depth_analysis` | Deep orderbook microstructure |

### crypto-technical (14 tools)

Source: CCXT + calculated. Technical indicators and pattern recognition.

| Tool | Description |
|---|---|
| `calculate_rsi` | Relative Strength Index (14, 21 periods) |
| `calculate_macd` | MACD with histogram and crossover signals |
| `calculate_bollinger_bands` | Bollinger Bands with squeeze detection |
| `detect_chart_patterns` | Double top/bottom, head & shoulders, triangles |
| `calculate_moving_averages` | Multiple MAs with crossover analysis |
| `get_support_resistance` | Key support/resistance levels |
| `calculate_fibonacci_levels` | Fibonacci retracement levels |
| `get_momentum_indicators` | Stochastic, Williams %R, ROC, CCI |
| `analyze_volume_profile` | Volume profile and high-volume zones |
| `detect_trend_reversals` | Multi-indicator reversal detection |
| `calculate_volatility` | Historical volatility, ATR, regime classification |
| `get_correlation_analysis` | Multi-asset correlation matrix |
| `generate_trading_signals` | Consensus signals with entry/SL/TP |
| `backtest_strategy` | Simple strategy backtesting (RSI, MACD, MA) |

### crypto-futures (10 tools)

Source: CCXT futures (Binance, Bybit, OKX, Bitget, MEXC). Perpetual futures data.

| Tool | Description |
|---|---|
| `get_funding_rate` | Current funding rate with annualized rate |
| `get_funding_rate_history` | Historical funding rates with statistics |
| `get_open_interest` | Open interest in USD and contracts |
| `get_long_short_ratio` | Top trader and global long/short ratio (Binance) |
| `get_taker_buy_sell_ratio` | Taker buy/sell volume ratio (Binance) |
| `calculate_liquidation_levels` | Estimated liquidation levels by leverage |
| `get_perpetual_stats` | Consolidated perpetual analysis with scoring |
| `compare_funding_rates` | Cross-exchange funding rate comparison |
| `analyze_funding_trend` | Funding rate trend analysis over time |
| `detect_funding_arbitrage` | Funding rate arbitrage opportunity detection |

### crypto-advanced-indicators (8 tools)

Source: CCXT + calculated. Advanced indicators not in the basic technical server.

| Tool | Description |
|---|---|
| `calculate_obv` | On-Balance Volume with divergence detection |
| `calculate_mfi` | Money Flow Index (RSI with volume) |
| `calculate_adx` | Average Directional Index (trend strength) |
| `calculate_ichimoku` | Ichimoku Cloud complete (Tenkan, Kijun, Senkou, Chikou) |
| `calculate_vwap` | Volume Weighted Average Price with bands |
| `calculate_pivot_points` | Classic pivot points (R1-R3, S1-S3) |
| `calculate_williams_r` | Williams %R momentum oscillator |
| `detect_divergences` | RSI/price divergence detection |

### crypto-market-microstructure (6 tools)

Source: CCXT orderbook data. Market microstructure analysis.

| Tool | Description |
|---|---|
| `analyze_orderbook_depth` | Orderbook liquidity and concentration analysis |
| `detect_orderbook_imbalance` | Bid/ask imbalance with direction prediction |
| `calculate_spread_metrics` | Spread, slippage, and execution cost estimation |
| `analyze_order_flow` | Taker aggression analysis from recent trades |
| `detect_spoofing_patterns` | Large suspicious order detection |
| `calculate_market_impact` | Price impact estimation for large orders |

---

## Skills

Skills are user-invocable slash commands defined in `skills/`. Each skill is a Markdown file with instructions the coordinator follows.

| Skill | File | Trigger |
|---|---|---|
| `/setup` | `skills/setup/SKILL.md` | First-time environment setup (cross-platform) |
| `/analyze` | `skills/analyze/SKILL.md` | Full 5-agent team analysis |
| `/quick` | `skills/quick/SKILL.md` | Single-agent market snapshot |
| `/portfolio` | `skills/portfolio/SKILL.md` | Portfolio status (read-only) |
| `/close-trade` | `skills/close-trade/SKILL.md` | Close trade + post-mortem + learning |
| `/validate-predictions` | `skills/validate-predictions/SKILL.md` | Review pending predictions |
| `/create` | `skills/create/SKILL.md` | Generate new components (MCP, agent, skill) |

---

## Portfolio and Paper Trading

All portfolio state lives in `data/trades/portfolio.json`. The portfolio-manager agent is the only agent authorized to write to this file.

### Portfolio Structure

- **Two portfolios:** spot (1x leverage only) and futures (variable leverage).
- **Initial balance:** $10,000 per portfolio.
- **Risk rules:** Max 3 open trades, max 50% allocation, mandatory stop-loss, minimum 2:1 R/R ratio.
- **Trade lifecycle:** Open -> Active -> Closed (with post-mortem).

### Decision Framework

Every full analysis ends with one of three decisions:

- **EXECUTE** -- Multiple strong signals align, R/R > 2:1, not overexposed.
- **WAIT** -- Signals positive but entry not optimal.
- **REJECT** -- Conflicting signals, poor R/R, or portfolio overexposed.

---

## Cognitive Learning System

The system implements a continuous learning loop that improves with every trade.

### Data Files

| File | Purpose |
|---|---|
| `data/trades/predictions.json` | Every testable prediction recorded at trade open, validated at close |
| `data/trades/agent-scorecards.json` | Per-agent accuracy tracking with confidence adjustments (0.5 to 1.5) |
| `data/trades/patterns.json` | Named patterns with win rates and SEEK/NEUTRAL/AVOID recommendations |

### Learning Loop

```
Trade Opens
    |
    v
learning-agent extracts predictions from agent_signals
    → writes to predictions.json
    |
    v
Trade Closes
    |
    v
learning-agent validates predictions against actual outcome
    → updates predictions.json (correct/incorrect)
    → updates agent-scorecards.json (accuracy, confidence_adjustment)
    → updates patterns.json (win rate, recommendation)
    |
    v
Next Analysis
    |
    v
portfolio-manager reads agent-scorecards.json
    → weights each agent's signals by confidence_adjustment
    → agents with high accuracy get more influence on decisions
```

### Agent Scorecards

Each agent has a `confidence_adjustment` score:
- Starts at 1.0 (neutral)
- +0.05 for each correct prediction (max 1.5)
- -0.1 for each incorrect prediction (min 0.5)
- Portfolio-manager uses these to weight signals when making EXECUTE/WAIT/REJECT decisions

### Pattern Library

Patterns are named trading setups with tracked win rates:
- **SEEK** (win rate > 60%) — actively look for this pattern
- **NEUTRAL** (win rate 40-60%) — proceed with caution
- **AVOID** (win rate < 40%) — do not trade this pattern

---

## Self-Evolving Platform (/create)

The `/create` skill enables the system to extend itself:

1. User describes a capability in natural language
2. system-builder agent (opus) researches APIs via WebSearch/WebFetch
3. Reads existing components to match patterns exactly
4. Generates the new component (MCP server, agent, or skill)
5. Reports integration steps to the user

The system-builder has `disallowedTools: Edit, Bash` — it can only create new files, never modify existing ones or execute commands. This is a safety boundary.

---

## News and Sentiment Design

The news-sentiment agent does NOT use any MCP server. Instead, it relies on Claude's native WebSearch and WebFetch tools.

This was a deliberate design decision. An earlier version used an MCP server with TextBlob + RSS feeds, but it was removed because:

1. RSS feeds are delayed and limited in scope.
2. TextBlob sentiment analysis is shallow keyword matching.
3. Claude's native NLP provides far superior semantic understanding of news impact.
4. WebSearch gives access to real-time breaking news, Twitter/X trends, and Reddit sentiment.

The news-sentiment agent is the only agent without MCP servers in its configuration.
