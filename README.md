# Crypto Trading Desk

**A multi-agent cryptocurrency intelligence system built entirely with Claude Code's native features.**

No orchestration code. No Python coordinator. No Agent SDK. Just Claude Code, 6 specialized agents, 6 MCP servers, and a CLAUDE.md file that turns them into a coordinated trading desk.

---

## Quick Start

**Prerequisites:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

```bash
# 1. Add the marketplace (one-time)
claude plugin marketplace add hugoguerrap/crypto-claude-desk

# 2. Install the plugin
claude plugin install crypto-trading-desk@hugoguerrap

# 3. Open Claude Code and try it
claude
```

```
/crypto-trading-desk:quick BTC
```

That's it. Python dependencies install automatically via `uv` the first time an MCP server is called (~30 sec). After that, everything is instant.

For a full 5-agent analysis with a trading decision:

```
/crypto-trading-desk:analyze ETH
```

---

## What Is This?

A paper-trading crypto analysis system where Claude Code acts as the coordinator for a team of AI agents. Each agent has a specific role -- from scanning live market data to running technical analysis to making final trading decisions -- and they communicate through shared report files on disk.

The system routes queries by complexity:

- **Quick** -- one agent, one answer, under 15 seconds.
- **Standard** -- 2-3 agents working in parallel, synthesized by the coordinator.
- **Full Analysis** -- a 5-agent team with DAG dependencies, producing a comprehensive report with an actionable EXECUTE / WAIT / REJECT decision.

---

## Architecture

```
User Query
    |
    v
[Claude Code - Coordinator]
    |  Reads CLAUDE.md for routing rules
    |  Classifies query complexity
    |
    +-- QUICK (1 agent) ------------------> market-monitor (haiku)
    |   "Price of BTC?"                      ~15 seconds
    |
    +-- STANDARD (2-3 agents parallel) ---> market-monitor + technical-analyst + news-sentiment
    |   "Analyze SOL"                        ~30-60 seconds
    |
    +-- FULL ANALYSIS (5-agent team) -----> Agent Team with DAG dependencies
        "/analyze ETH"                       ~3-5 minutes
        |
        |   Phase 1 (parallel)
        |   +-- market-monitor ---------> market-data.md
        |   +-- technical-analyst ------> technical-analysis.md
        |   +-- news-sentiment ---------> news-sentiment.md
        |
        |   Phase 2 (after Phase 1)
        |   +-- risk-specialist --------> risk-assessment.md
        |
        |   Phase 3 (after Phase 2)
        |   +-- portfolio-manager ------> decision.md
        |
        v
    Reports saved to data/reports/YYYY-MM-DD-{symbol}/
```

### Agents

| Agent | Model | Role |
|---|---|---|
| market-monitor | haiku | Live prices, volume, Fear & Greed, funding rates, whale alerts, arbitrage |
| technical-analyst | sonnet | RSI, MACD, Bollinger, Ichimoku, VWAP, patterns, support/resistance, signals |
| news-sentiment | sonnet | Breaking news, social sentiment, regulatory updates, FUD/FOMO detection |
| risk-specialist | sonnet | Volatility, VaR, correlation, orderbook depth, spoofing detection, position sizing |
| portfolio-manager | opus | Final EXECUTE/WAIT/REJECT decision, paper trade execution, portfolio state |
| learning-agent | haiku | Pre-trade pattern lookup, post-trade analysis, agent accuracy grading |

### MCP Servers

| Server | Tools | Data Source |
|---|---|---|
| crypto-data | 12 | CoinGecko API (Fear & Greed, dominance, rankings, categories) |
| crypto-exchange | 16 | CCXT multi-exchange (Binance, Kraken, Bitfinex, KuCoin, MEXC) |
| crypto-technical | 14 | CCXT + calculated (RSI, MACD, Bollinger, patterns, backtesting) |
| crypto-futures | 10 | CCXT futures (funding rates, open interest, long/short, liquidations) |
| crypto-advanced-indicators | 8 | CCXT (OBV, MFI, ADX, Ichimoku, VWAP, Pivot Points, divergences) |
| crypto-market-microstructure | 6 | CCXT (orderbook depth, imbalance, spread, spoofing, market impact) |

**Total: 66 MCP tools** across 6 servers, all powered by public APIs with no API keys required.

---

## Available Commands

When installed as a plugin, commands are namespaced:

| Command | Description | Agents Used |
|---|---|---|
| `/crypto-trading-desk:quick BTC` | Fast market snapshot | market-monitor (1 agent) |
| `/crypto-trading-desk:analyze ETH` | Full analysis with trading decision | All 5 agents (Agent Team) |
| `/crypto-trading-desk:portfolio` | View balances, open trades, P&L | portfolio-manager |
| `/crypto-trading-desk:close-trade trade_001` | Close trade with post-mortem | portfolio-manager + learning-agent |

You can also ask in natural language. The coordinator routes by complexity:

- *"How's BTC?"* --> Quick (market-monitor only)
- *"RSI of ETH?"* --> Standard (technical-analyst only)
- *"Should I buy SOL?"* --> Full Analysis (5-agent team)
- *"Check my portfolio"* --> portfolio-manager

---

## How It Works

### What happens when you install

1. `claude plugin marketplace add hugoguerrap/crypto-claude-desk` -- adds the marketplace.
2. `claude plugin install crypto-trading-desk@hugoguerrap` -- clones the repo into `~/.claude/plugins/cache/crypto-trading-desk/`.
3. First new session: `SessionStart` hook creates `data/` directories and `portfolio.json` (~10ms).
4. First MCP call: `uv run` detects no virtual environment, creates one, installs Python dependencies from `pyproject.toml` (~30 sec). After this, all MCP calls are instant.

### How dependencies are managed

The 6 MCP servers need Python packages (ccxt, fastmcp, numpy, pandas). The plugin uses `uv run --project ${CLAUDE_PLUGIN_ROOT}` which automatically:
1. Creates a `.venv/` inside the plugin cache (first time only)
2. Installs all dependencies from `pyproject.toml`
3. Runs the MCP server

`${CLAUDE_PLUGIN_ROOT}` is a variable Claude Code expands to the plugin's install directory. No hardcoded paths.

### Plugin structure

```
crypto-trading-desk/
├── .claude-plugin/
│   ├── plugin.json              # Plugin manifest
│   └── marketplace.json         # Marketplace definition
├── agents/                      # 6 agent definitions (.md with YAML frontmatter)
│   ├── market-monitor.md
│   ├── technical-analyst.md
│   ├── news-sentiment.md
│   ├── risk-specialist.md
│   ├── portfolio-manager.md
│   └── learning-agent.md
├── skills/                      # 4 slash commands
│   ├── analyze/SKILL.md
│   ├── quick/SKILL.md
│   ├── portfolio/SKILL.md
│   └── close-trade/SKILL.md
├── hooks/
│   ├── hooks.json               # SessionStart hook
│   └── post-setup.sh            # Creates data dirs (~10ms)
├── mcp-servers/                 # 6 Python MCP servers (66 tools)
├── mcp-servers.plugin.json      # MCP config (uv run + ${CLAUDE_PLUGIN_ROOT})
├── pyproject.toml               # Python dependencies
├── CLAUDE.md                    # Routing logic and coordination rules
└── data/
    ├── trades/portfolio.json.example
    └── reports/
```

### Recommended settings

Add to your Claude Code settings (`~/.claude/settings.json`) for the best experience:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "permissions": {
    "allow": [
      "mcp__crypto-data",
      "mcp__crypto-exchange",
      "mcp__crypto-technical",
      "mcp__crypto-futures",
      "mcp__crypto-advanced-indicators",
      "mcp__crypto-market-microstructure",
      "WebSearch",
      "WebFetch"
    ]
  }
}
```

Without these, Claude Code will prompt you to approve each MCP tool on first use, and Agent Teams (needed for `/analyze`) won't be available.

---

## Design Principles

1. **Zero orchestration code.** Claude Code is the coordinator. CLAUDE.md contains all routing logic. Agents are markdown files with YAML frontmatter.

2. **Model optimization.** Haiku for data scouts, Sonnet for analysis, Opus for final decisions. ~40-60% token savings vs running everything on a single model tier.

3. **File-based coordination.** Agents write report files to `data/reports/`. Phase 2+ agents read Phase 1 files directly from disk. No message passing, no shared state.

4. **Principle of least privilege.** Each agent has `disallowedTools` restricting access to only what it needs.

5. **Persistent memory.** The portfolio-manager and learning-agent use `memory: project` to build institutional knowledge across sessions.

---

## Extending the System

See [docs/extending.md](docs/extending.md) for guides on adding agents, MCP servers, skills, and exchanges.

For a deep technical overview, see [docs/architecture.md](docs/architecture.md).

### Local development

```bash
# Test changes without installing
claude --plugin-dir /path/to/crypto-trading-desk
```

---

## Disclaimer

This is a **paper trading system only**. No real money is at risk. All trades are simulated in `data/trades/portfolio.json`.

This project is for educational and experimental purposes. It is not financial advice.

---

## License

[MIT License](LICENSE)
