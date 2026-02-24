# Crypto Trading Desk - Multi-Agent Intelligence System

A cryptocurrency analysis system built with Claude Code's native features: agents, MCP servers, and skills.

## Architecture

```
User Query
    |
    v
[Claude Code - Coordinator]
    |  Reads this CLAUDE.md
    |  Routes by complexity:
    |
    +-- QUICK (1 subagent) ----------> market-monitor (haiku)
    |
    +-- STANDARD (2-3 parallel) -----> market-monitor + technical-analyst + news-sentiment
    |
    +-- FULL ANALYSIS (5 subagents) -> 3 phases with file-based coordination
         Phase 1 (parallel): market-monitor || technical-analyst || news-sentiment
         Phase 2 (sequential): risk-specialist (reads Phase 1 files)
         Phase 3 (sequential): portfolio-manager (reads all, decides)
```

## How to Use

### First-Time Setup
- `/setup` - **Run once after installing.** Detects environment, installs uv + Python deps, verifies MCP servers work. Cross-platform (macOS, Linux, Windows).

### Slash Commands
- `/quick BTC` - Fast market snapshot (1 agent, ~15 sec)
- `/analyze BTC` - Full 5-agent analysis with trading decision (~3-5 min)
- `/portfolio` - View portfolio status and open trades
- `/close-trade trade_001` - Close trade with post-mortem
- `/validate-predictions` - Review pending predictions against market data
- `/monitor` - Autonomous loop: check SL/TP, close trades, evaluate predictions
- `/create` - Extend the system with new components

### Natural Language
Ask naturally and the coordinator routes by complexity:
- "How's BTC?" → Quick (market-monitor only)
- "RSI of ETH?" → Standard (technical-analyst only)
- "Analyze SOL" → Standard (2-3 agents)
- "Full analysis of BTC with recommendation" → Full (5 agents in phases)
- "Check my portfolio" → portfolio-manager
- "Post-mortem on trade_003" → learning-agent

## Routing Rules

### How Delegation Works

All agents are spawned via the Task tool with `subagent_type: general-purpose` and an explicit `model` parameter. This ensures every subagent inherits all MCP tools from the parent conversation. The agent `.md` files in `agents/` contain the analysis framework — include "Read agents/{name}.md for your full analysis framework" in the prompt.

> **Why `general-purpose`?** Plugin-defined agent types (e.g., `crypto-trading-desk:market-monitor`) don't receive MCP tools due to a known Claude Code limitation ([#4476](https://github.com/anthropics/claude-code/issues/4476)). Using `general-purpose` with explicit `model` works in both plugin and local-clone modes.

Always include "Do NOT use the Edit tool" in every agent prompt.

### Quick Query (single subagent via Task tool)
Use for simple data points. One agent, fast response.

| Query Type | Role | Model | Key MCP tools to mention in prompt |
|-----------|------|-------|-----------------------------------|
| Price, volume, market overview | market-monitor | haiku | crypto-exchange, crypto-data, crypto-futures |
| RSI, MACD, indicators, patterns | technical-analyst | sonnet | crypto-technical, crypto-advanced-indicators |
| News, sentiment, FUD/FOMO | news-sentiment | sonnet | WebSearch, WebFetch (no MCP needed) |
| Portfolio status, trade history | portfolio-manager | opus | crypto-learning-db, crypto-exchange |
| Pattern lookup, pre-trade check | learning-agent | opus | crypto-learning-db, crypto-data |

Example delegation:
```
Task(subagent_type="general-purpose", model="haiku", prompt="You are the market-monitor agent. Read agents/market-monitor.md for your framework. Get BTC price using get_exchange_prices(symbol='BTC/USDT')... Do NOT use the Edit tool.")
```

### Standard Analysis (2-3 subagents in parallel)
Use for "analyze X" without explicit "full analysis" or "recommendation" request.
Launch 3 Tasks in parallel (all `subagent_type: general-purpose`):
- market-monitor (model: haiku) + technical-analyst (model: sonnet) + news-sentiment (model: sonnet)
- Coordinator synthesizes results

### Full Analysis with Decision (5 subagents in phases)
Use for "full analysis", "should I buy", "recommendation", or `/analyze`.
Spawn 5 subagents via the Task tool in **3 sequential phases** (see `/analyze` skill for detailed prompts):

**Phase 1 - Data Gathering (3 Tasks in parallel):**
- market-monitor (haiku) → `data/reports/YYYY-MM-DD-{symbol}/market-data.md`
- technical-analyst (sonnet) → `data/reports/YYYY-MM-DD-{symbol}/technical-analysis.md`
- news-sentiment (sonnet) → `data/reports/YYYY-MM-DD-{symbol}/news-sentiment.md`

**Wait for all 3 Task calls to return. Verify files exist on disk.**

**Phase 2 - Risk Assessment (1 Task AFTER Phase 1):**
- risk-specialist (sonnet) reads Phase 1 files → `data/reports/YYYY-MM-DD-{symbol}/risk-assessment.md`

**Wait for Task to return. Verify file exists.**

**Phase 3 - Decision (1 Task AFTER Phase 2):**
- portfolio-manager (opus) reads all files → `data/reports/YYYY-MM-DD-{symbol}/decision.md`

**IMPORTANT:** Do NOT spawn all 5 agents at once. Phase 2/3 agents MUST read files written by previous phases. Spawn them only after confirming previous phase files exist on disk.

### Special Queries (single subagent)
- "Close trade X" → portfolio-manager (close) + learning-agent (post-mortem + prediction validation)
- "What patterns have we seen?" → learning-agent
- "Check my predictions" → learning-agent via /validate-predictions
- "Risk on my position?" → risk-specialist
- "Monitor my trades" / "Check SL/TP" → /monitor (multi-agent coordination)
- "Create a new MCP/agent/skill" → system-builder via /create

## Delegation Rules

**ALWAYS delegate via Task with `subagent_type: general-purpose` and explicit `model`.** Include the agent's role and relevant MCP tools in the prompt. Don't call MCP tools directly from the main conversation.

**NEVER over-delegate.** If someone asks "price of BTC?", use one haiku agent. Don't spin up 5 agents for a simple question.

**After every trade close, ALWAYS delegate to learning-agent** for prediction validation. This is how the system learns.

## Agents (7)

| Agent | Role | Model | MCPs | Native Tools |
|-------|------|-------|------|-------------|
| market-monitor | Fast market data, whale alerts, arbitrage scan | haiku | data, futures, exchange | WebSearch, Read |
| technical-analyst | Indicators, patterns, signals | sonnet | technical, advanced-indicators, exchange, data, learning-db | WebSearch, Read |
| news-sentiment | News + social sentiment + crowd psychology | sonnet | learning-db | WebSearch, WebFetch, Read |
| risk-specialist | Risk, volatility, microstructure, institutional flows | sonnet | technical, microstructure, data, exchange, learning-db | WebSearch, Read |
| portfolio-manager | Final decisions + trade execution | opus | data, learning-db | Read, Grep, Write |
| learning-agent | Predictions, patterns, post-mortem | opus | data, learning-db | Read, Grep, Write |
| system-builder | Generate new MCP servers, agents, skills + tests | opus | (none) | Read, Write, Grep, Glob, WebSearch, WebFetch |

## MCP Servers (7)

| Server | Tools | Data Source |
|--------|-------|-------------|
| crypto-data | 11 | CoinGecko API (market metadata: fear/greed, dominance, rankings — NOT for live prices) |
| crypto-exchange | 16 | CCXT multi-exchange (orderbooks, OHLCV, volume, arbitrage) |
| crypto-technical | 14 | CCXT + calculated (RSI, MACD, Bollinger, patterns, signals) |
| crypto-futures | 10 | CCXT futures (funding rates, OI, long/short, liquidations) |
| crypto-advanced-indicators | 8 | CCXT (OBV, MFI, ADX, Ichimoku, VWAP, Pivot Points) |
| crypto-market-microstructure | 6 | CCXT (orderbook depth, imbalance, spoofing, market impact) |
| crypto-learning-db | 18 | SQLite (trades, predictions, patterns, summaries, track records, trade modifications) |

> **Note:** News and sentiment analysis uses WebSearch + WebFetch directly (Claude's native web intelligence) instead of MCP. This provides real-time breaking news, social sentiment from Twitter/Reddit, and semantic understanding superior to RSS-based keyword matching.

## Skills (8)

| Skill | Usage | Description |
|-------|-------|-------------|
| `/setup` | `/setup` | First-time environment setup (cross-platform) |
| `/analyze` | `/analyze BTC` | Full 5-agent phased analysis with decision |
| `/quick` | `/quick ETH` | Fast single-agent market check |
| `/portfolio` | `/portfolio` | Portfolio status and open trades |
| `/close-trade` | `/close-trade trade_001` | Close trade with post-mortem + learning |
| `/validate-predictions` | `/validate-predictions` | Review pending predictions against market data |
| `/monitor` | `/monitor` | Autonomous loop: check SL/TP, close trades, evaluate predictions, generate summaries |
| `/create` | `/create a DeFi tracker` | Extend the system with new components (+ tests for MCP servers) |

## Design Decisions

1. **Hybrid routing** — Quick queries use single subagents (cheap, fast). Full analysis uses 5 phased subagents (parallel where possible, sequential where needed).
2. **Model optimization** — haiku for data scouts, sonnet for analysis, opus for final decisions. ~40-60% token savings vs all-sonnet. Model is passed explicitly via Task `model` parameter.
3. **General-purpose subagents** — All agents use `subagent_type: general-purpose` to inherit MCP tools. Plugin agent types don't pass MCP tools to subagents ([Claude Code #4476](https://github.com/anthropics/claude-code/issues/4476)). Agent `.md` files define the analysis framework; the coordinator includes their instructions in the Task prompt.
4. **Persistent memory** — portfolio-manager and learning-agent use `memory: project` to build institutional knowledge across sessions.
5. **File-based coordination** — Agents write structured Markdown reports to a shared directory. Later-phase agents read those files before starting their analysis.
6. **Zero orchestration code** — No Python coordinator, no Agent SDK. Claude Code is the coordinator via CLAUDE.md + agents/.
7. **Dual distribution** — Works as a Claude Code plugin (`claude plugin install`) or as a local clone (`--plugin-dir`). Both modes use the same `general-purpose` delegation pattern.
8. **SQLite cognitive memory** — Trades, predictions, and patterns stored in SQLite (`data/db/learning.db`). Agents query only what they need via `crypto-learning-db` MCP, preventing context window overflow. Scales to unlimited trades.

## Cognitive Learning System

The system learns from every trade through a **SQLite-backed cognitive memory** (`crypto-learning-db` MCP server).

### Storage: SQLite Database (`data/db/learning.db`)

| Table | Purpose |
|-------|---------|
| `trades` | All open and closed trades with full metadata |
| `predictions` | Testable predictions from each agent (with NL evaluations) |
| `trade_modifications` | SL/TP change history with NL reasons |
| `patterns` | Named trading patterns with win rates |
| `summaries` | Monthly/quarterly performance summaries |
| `portfolio_state` | Current balances and aggregate stats |

### Three Learning Layers

1. **Operational memory** (SQLite queries): What the agent needs right now for a specific decision
2. **Strategic memory** (summaries table): Compressed knowledge from past periods, generated via `generate_summary()`
3. **Meta-learning** (`get_prediction_track_record()`): "How reliable is this type of setup in these conditions?"

### Adaptive Learning (NL-driven)

The system learns through **natural language reasoning, not formulas**. MCP tools store data; agents do all interpretation.

- `validate_prediction(evaluation="...")` stores the learning-agent's NL analysis of how close a prediction was and why. No formulas, no credit scores — just the agent's written reasoning.
- `get_prediction_track_record(symbol="...", strategy_type="...")` provides setup-centric accuracy by time window (7d, 30d, 90d, global) PLUS recent NL evaluations. The key question is "how reliable is this setup?" not "how much do I trust this agent?"
- `find_expired_predictions()` surfaces predictions past their timeframe with price context. The agent evaluates each one and validates.
- portfolio-manager reads track records + evaluations and reasons in NL about setup reliability. Claude is the consensus engine.

### Learning Loop

Open trade → `record_trade()` + `record_prediction()` → close trade → `close_trade()` + `validate_prediction(evaluation="...")` → NL evaluation stored → `upsert_pattern()` → `generate_summary()` periodically → next trade: `get_prediction_track_record()` returns setup accuracy + evaluations → agent reasons about setup reliability → `find_expired_predictions()` catches missed validations.

## Headless / Autopilot Mode

Skills are **NOT** invoked via `/skill-name` in `-p` (print) mode. For scheduled execution via cron, use `bin/autopilot.sh` which maps workflow names to detailed natural language prompts:

```bash
./bin/autopilot.sh monitor           # Check SL/TP, close trades, evaluate
./bin/autopilot.sh quick "BTC ETH"   # Fast market snapshot
./bin/autopilot.sh analyze "BTC"     # Full 5-agent analysis
./bin/autopilot.sh portfolio         # Portfolio status
```

The wrapper handles PATH, working directory, tool permissions (`--allowedTools`), and logging.

## Output Guidelines

- Data-driven analysis with specific numbers
- Actionable insights, not generic commentary
- Risk parameters on every trade suggestion
- Reports saved to `data/reports/` for full analyses
- Learning-agent builds pattern library over time via persistent memory
