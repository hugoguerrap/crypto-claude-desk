# Crypto Trading Desk - Multi-Agent Intelligence System

A cryptocurrency analysis system built with Claude Code's native features: agents, MCPs, skills, and Agent Teams.

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
    +-- FULL ANALYSIS (Agent Team) --> 5 teammates with DAG dependencies
         Phase 1 (parallel): market-monitor || technical-analyst || news-sentiment
         Phase 2 (sequential): risk-specialist (reads Phase 1 files)
         Phase 3 (sequential): portfolio-manager (reads all, decides)
```

## How to Use

### First-Time Setup
- `/setup` - **Run once after installing.** Detects environment, installs uv + Python deps, verifies MCP servers work. Cross-platform (macOS, Linux, Windows).

### Slash Commands
- `/quick BTC` - Fast market snapshot (1 agent, ~15 sec)
- `/analyze BTC` - Full analysis with Agent Team (5 agents, ~3-5 min)
- `/portfolio` - View portfolio status and open trades
- `/close-trade trade_001` - Close trade with post-mortem

### Natural Language
Ask naturally and the coordinator routes by complexity:
- "How's BTC?" → Quick (market-monitor only)
- "RSI of ETH?" → Standard (technical-analyst only)
- "Analyze SOL" → Standard (2-3 agents)
- "Full analysis of BTC with recommendation" → Full (Agent Team, 5 agents)
- "Check my portfolio" → portfolio-manager
- "Post-mortem on trade_003" → learning-agent

## Routing Rules

### Quick Query (single subagent via Task tool)
Use for simple data points. One agent, fast response.

| Query Type | Agent | Model |
|-----------|-------|-------|
| Price, volume, market overview | market-monitor | haiku |
| RSI, MACD, indicators, patterns | technical-analyst | sonnet |
| News, sentiment, FUD/FOMO | news-sentiment | sonnet |
| Portfolio status, trade history | portfolio-manager | opus |
| Pattern lookup, pre-trade check | learning-agent | haiku |

### Standard Analysis (2-3 subagents in parallel)
Use for "analyze X" without explicit "full analysis" or "recommendation" request.
Launch in parallel via Task tool:
- market-monitor + technical-analyst + news-sentiment
- Coordinator synthesizes results

### Full Analysis with Decision (Agent Team)
Use for "full analysis", "should I buy", "recommendation", or `/analyze`.
Creates Agent Team with 5 teammates and **sequential phase spawning**:

**Phase 1 - Data Gathering (spawn 3 agents in parallel):**
- market-monitor → `data/reports/YYYY-MM-DD-{symbol}/market-data.md`
- technical-analyst → `data/reports/YYYY-MM-DD-{symbol}/technical-analysis.md`
- news-sentiment → `data/reports/YYYY-MM-DD-{symbol}/news-sentiment.md`

**Wait for Phase 1 completion (or 5min timeout for news-sentiment)**

**Phase 2 - Risk Assessment (spawn AFTER Phase 1 completes):**
- risk-specialist reads Phase 1 files → `data/reports/YYYY-MM-DD-{symbol}/risk-assessment.md`

**Wait for Phase 2 completion**

**Phase 3 - Decision (spawn AFTER Phase 2 completes):**
- portfolio-manager reads all files → `data/reports/YYYY-MM-DD-{symbol}/decision.md`

**IMPORTANT:** Do NOT spawn all 5 agents at once. Spawn Phase 2/3 agents only after confirming previous phase files exist on disk.

### Special Queries (single subagent)
- "Close trade X" → portfolio-manager (close) + learning-agent (post-mortem + prediction validation + scorecard update)
- "What patterns have we seen?" → learning-agent
- "Check my predictions" → learning-agent via /validate-predictions
- "Risk on my position?" → risk-specialist
- "Create a new MCP/agent/skill" → system-builder via /create

## Delegation Rules

**ALWAYS delegate to agents for analysis.** Don't call MCP tools directly from the main conversation. Each agent knows which MCPs to use and how to parallelize calls.

**NEVER over-delegate.** If someone asks "price of BTC?", use market-monitor alone. Don't spin up 5 agents for a simple question.

**Agent Team only for full analysis.** Quick and standard queries use plain Task tool subagents. Agent Teams add coordination overhead that's only justified for comprehensive analysis with decision-making.

**After every trade close, ALWAYS delegate to learning-agent** for prediction validation and scorecard update. This is how the system learns.

## Agents (7)

| Agent | Role | Model | MCPs | Native Tools |
|-------|------|-------|------|-------------|
| market-monitor | Fast market data, whale alerts, arbitrage scan | haiku | data, futures, exchange | WebSearch, Read |
| technical-analyst | Indicators, patterns, signals | sonnet | technical, advanced-indicators, exchange, data | WebSearch, Read |
| news-sentiment | News + social sentiment + crowd psychology | sonnet | (none - uses WebSearch/WebFetch) | WebSearch, WebFetch, Read |
| risk-specialist | Risk, volatility, microstructure, institutional flows | sonnet | technical, microstructure, data, exchange | WebSearch, Read |
| portfolio-manager | Final decisions + trade execution | opus | data | Read, Grep, Write |
| learning-agent | Predictions, scorecards, patterns, post-mortem | haiku | data | Read, Grep, Write |
| system-builder | Generate new MCP servers, agents, skills | opus | (none) | Read, Write, Grep, Glob, WebSearch, WebFetch |

## MCP Servers (6)

| Server | Tools | Data Source |
|--------|-------|-------------|
| crypto-data | 11 | CoinGecko API (market metadata: fear/greed, dominance, rankings — NOT for live prices) |
| crypto-exchange | 16 | CCXT multi-exchange (orderbooks, OHLCV, volume, arbitrage) |
| crypto-technical | 14 | CCXT + calculated (RSI, MACD, Bollinger, patterns, signals) |
| crypto-futures | 10 | CCXT futures (funding rates, OI, long/short, liquidations) |
| crypto-advanced-indicators | 8 | CCXT (OBV, MFI, ADX, Ichimoku, VWAP, Pivot Points) |
| crypto-market-microstructure | 6 | CCXT (orderbook depth, imbalance, spoofing, market impact) |

> **Note:** News and sentiment analysis uses WebSearch + WebFetch directly (Claude's native web intelligence) instead of MCP. This provides real-time breaking news, social sentiment from Twitter/Reddit, and semantic understanding superior to RSS-based keyword matching.

## Skills (7)

| Skill | Usage | Description |
|-------|-------|-------------|
| `/setup` | `/setup` | First-time environment setup (cross-platform) |
| `/analyze` | `/analyze BTC` | Full Agent Team analysis with decision |
| `/quick` | `/quick ETH` | Fast single-agent market check |
| `/portfolio` | `/portfolio` | Portfolio status and open trades |
| `/close-trade` | `/close-trade trade_001` | Close trade with post-mortem + learning |
| `/validate-predictions` | `/validate-predictions` | Review pending predictions against market data |
| `/create` | `/create a DeFi tracker` | Extend the system with new components |

## Design Decisions

1. **Hybrid routing** — Quick queries use single subagents (cheap, fast). Full analysis uses Agent Teams (parallel, coordinated).
2. **Model optimization** — haiku for data scouts, sonnet for analysis, opus for final decisions. ~40-60% token savings vs all-sonnet.
3. **Agent Teams for full analysis** — 5 teammates with DAG dependencies enable true parallel execution and inter-agent communication.
4. **Persistent memory** — portfolio-manager and learning-agent use `memory: project` to build institutional knowledge across sessions.
5. **Principle of least privilege** — Each agent has `disallowedTools` to restrict access to only what they need.
6. **File-based coordination** — Agent Team teammates write to shared report files. Phase 2+ agents read Phase 1 files directly.
7. **Zero orchestration code** — No Python coordinator, no Agent SDK. Claude Code is the coordinator via CLAUDE.md + agents/.
8. **Plugin-native distribution** — Distributed as a Claude Code plugin (`claude plugin install`). Agents, skills, hooks, and MCP servers are auto-discovered from standard plugin directories.

## Cognitive Learning System

The system learns from every trade through structured data:

- **`data/trades/predictions.json`** — Every agent prediction is recorded when a trade opens and validated when it closes.
- **`data/trades/agent-scorecards.json`** — Each agent has an accuracy score and confidence adjustment (0.5 to 1.5). Portfolio-manager uses these to weight signals.
- **`data/trades/patterns.json`** — Named trading patterns with win rates, conditions, and SEEK/NEUTRAL/AVOID recommendations.

**Learning loop:** Open trade → record predictions → close trade → validate predictions → update scorecards → update patterns → next trade uses adjusted weights.

## Output Guidelines

- Data-driven analysis with specific numbers
- Actionable insights, not generic commentary
- Risk parameters on every trade suggestion
- Reports saved to `data/reports/` for full analyses
- Learning-agent builds pattern library over time via persistent memory
