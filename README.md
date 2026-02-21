# Crypto Trading Desk

**A multi-agent cryptocurrency intelligence system built entirely with Claude Code's native features.**

No orchestration code. No Python coordinator. No Agent SDK. Just Claude Code, 6 specialized agents, 6 MCP servers, and a CLAUDE.md file that turns them into a coordinated trading desk.

---

## What Is This?

Crypto Trading Desk is a paper-trading crypto analysis system where Claude Code acts as the coordinator for a team of AI agents. Each agent has a specific role -- from scanning live market data to running technical analysis to making final trading decisions -- and they communicate through shared report files on disk.

The system routes queries by complexity:

- **Quick** -- one agent, one answer, under 15 seconds.
- **Standard** -- 2-3 agents working in parallel, synthesized by the coordinator.
- **Full Analysis** -- a 5-agent team with DAG dependencies, producing a comprehensive report with an actionable EXECUTE / WAIT / REJECT decision.

Everything runs through Claude Code's native primitives: agents, MCP servers, skills, and Agent Teams. There is zero custom orchestration code.

---

## Quick Start

### Option A: Install as Plugin (Recommended)

**Prerequisites:** [uv](https://docs.astral.sh/uv/) (Python package manager). Install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`

```bash
# 1. Add the marketplace (one-time)
claude plugin marketplace add hugoguerrap/crypto-claude-desk

# 2. Install the plugin
claude plugin install crypto-claude-desk@hugoguerrap
```

Or from the TUI:
```
/plugin  →  Discover tab  →  crypto-trading-desk  →  Install
```

That's it. Python dependencies install automatically via `uv` the first time an MCP server is called. Skills appear as `/crypto-trading-desk:quick`, `/crypto-trading-desk:analyze`, etc.

**For local development:**
```bash
claude --plugin-dir ./crypto-trading-desk
```

### Option B: Standalone (Clone & Run)

```bash
# 1. Clone the repository
git clone https://github.com/hugoguerrap/crypto-claude-desk.git
cd crypto-trading-desk

# 2. Run setup (creates venv, installs dependencies, configures MCP servers)
chmod +x setup.sh
./setup.sh            # uses pip
# or: ./setup.sh --uv  # uses uv (faster)

# 3. Launch Claude Code in the project directory
claude
```

Once inside Claude Code, try:

```
/quick BTC
```

Or for a full 5-agent analysis with a trading decision:

```
/analyze ETH
```

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
        "Full analysis of BTC"               ~3-5 minutes
        "/analyze ETH"
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

| Command | Description | Agents Used |
|---|---|---|
| `/quick BTC` | Fast market snapshot | market-monitor (1 agent) |
| `/analyze ETH` | Full analysis with trading decision | All 5 agents (Agent Team) |
| `/portfolio` | View balances, open trades, P&L | portfolio-manager |
| `/close-trade trade_001` | Close trade with post-mortem | portfolio-manager + learning-agent |

You can also ask in natural language. The coordinator routes by complexity:

- *"How's BTC?"* --> Quick (market-monitor only)
- *"RSI of ETH?"* --> Standard (technical-analyst only)
- *"Should I buy SOL?"* --> Full Analysis (5-agent team)
- *"Check my portfolio"* --> portfolio-manager
- *"Post-mortem on trade_003"* --> learning-agent

---

## Design Principles

1. **Zero orchestration code.** Claude Code is the coordinator. CLAUDE.md contains all routing logic. Agents are markdown files in `.claude/agents/`. Works both as a standalone project and as a Claude Code plugin.

2. **Model optimization.** Haiku for data scouts, Sonnet for analysis, Opus for final decisions. This achieves 40-60% token savings compared to running everything on a single model tier.

3. **File-based coordination.** In a Full Analysis, agents write report files to `data/reports/`. Phase 2+ agents read Phase 1 files directly from disk. No message passing, no shared state -- just files.

4. **Principle of least privilege.** Each agent has `disallowedTools` restricting access to only what it needs. The learning-agent cannot write files. The market-monitor cannot edit files.

5. **Persistent memory.** The portfolio-manager and learning-agent use `memory: project` to build institutional knowledge across sessions -- tracking patterns, win rates, and lessons learned.

---

## Extending the System

See [docs/extending.md](docs/extending.md) for detailed guides on:

- Adding a new agent
- Adding a new MCP server
- Adding a new skill (slash command)
- Modifying routing rules
- Adding exchange support

For a deep technical overview, see [docs/architecture.md](docs/architecture.md).

---

## Plugin Architecture

This project is designed as a **dual-mode** Claude Code plugin: it works both when installed as a plugin (`claude plugin install`) and when cloned as a standalone project (`git clone` + `setup.sh`). This section explains how.

### Why Dual-Mode?

Most Claude Code plugins are single-purpose (one MCP server, one hook). This project is different -- it includes 6 agents, 4 skills, 6 MCP servers, and hooks. We want two things:

1. **Plugin users** can install it with one command and everything works.
2. **Developers** can clone the repo, modify agents/MCP servers, and run it directly.

The challenge is that Claude Code looks for agents in different locations depending on the mode:

| Component | Standalone (project) | Plugin (installed) |
|---|---|---|
| Agents | `.claude/agents/` | `agents/` at plugin root |
| Skills | `.claude/skills/` | `skills/` at plugin root |
| Settings | `.claude/settings.json` | `settings.json` at plugin root |
| MCP config | `.mcp.json` at project root | `.mcp.json` at plugin root |

Our solution: keep agents and skills in `.claude/` (so standalone mode works out of the box), and tell the plugin system where to find them via `plugin.json`:

```json
{
  "name": "crypto-trading-desk",
  "agents": "./.claude/agents/",
  "skills": "./.claude/skills/",
  "mcpServers": "./mcp-servers.plugin.json"
}
```

This way both modes find the same files. No symlinks, no file duplication.

### Project Structure

```
crypto-trading-desk/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest — points to components below
│
├── .claude/
│   ├── agents/                  # 6 agent .md files (shared by both modes)
│   │   ├── market-monitor.md
│   │   ├── technical-analyst.md
│   │   ├── news-sentiment.md
│   │   ├── risk-specialist.md
│   │   ├── portfolio-manager.md
│   │   └── learning-agent.md
│   ├── skills/                  # 4 skill directories (shared by both modes)
│   │   ├── analyze/SKILL.md
│   │   ├── quick/SKILL.md
│   │   ├── portfolio/SKILL.md
│   │   └── close-trade/SKILL.md
│   └── settings.json            # Permissions + env vars (standalone mode only)
│
├── hooks/
│   ├── hooks.json               # SessionStart hook definition
│   └── post-setup.sh            # Creates data dirs on first session (~10ms)
│
├── mcp-servers/                 # 6 Python MCP servers (66 tools total)
│   ├── validators.py            # Shared input validation module
│   ├── crypto_ultra_simple.py   # CoinGecko API (12 tools)
│   ├── crypto_exchange_ccxt_ultra.py  # CCXT multi-exchange (16 tools)
│   ├── crypto_technical_analysis.py   # Technical analysis (14 tools)
│   ├── crypto_futures_data.py         # Futures data (10 tools)
│   ├── crypto_advanced_indicators.py  # Advanced indicators (8 tools)
│   └── crypto_market_microstructure.py # Microstructure (6 tools)
│
├── mcp-servers.plugin.json      # MCP config for plugin mode (uses uv)
├── .mcp.json.template           # MCP config template for standalone mode (uses pip/venv)
├── pyproject.toml               # Python dependencies for uv
├── requirements.txt             # Python dependencies for pip
├── setup.sh                     # Standalone setup script
├── CLAUDE.md                    # Routing logic and agent coordination rules
└── data/
    ├── trades/portfolio.json    # Paper trading state (gitignored)
    └── reports/                 # Agent output files (gitignored)
```

### How Dependencies Work in Each Mode

The 6 MCP servers need Python packages (ccxt, fastmcp, numpy, pandas, etc.). Each mode handles this differently:

**Plugin mode** uses [uv](https://docs.astral.sh/uv/), the fast Python package manager. The MCP config calls `uv run --project ${CLAUDE_PLUGIN_ROOT}`, which automatically:
1. Creates a virtual environment (first time only)
2. Installs all dependencies from `pyproject.toml`
3. Runs the MCP server

No manual setup. The first MCP call takes ~30 seconds (dependency install), then it's instant.

`${CLAUDE_PLUGIN_ROOT}` is a special variable that Claude Code expands to the plugin's install directory (e.g., `~/.claude/plugins/cache/crypto-trading-desk/`). This makes all paths portable.

**Standalone mode** uses `setup.sh`, which:
1. Creates a Python venv
2. Installs dependencies via `pip install -r requirements.txt`
3. Generates `.mcp.json` from `.mcp.json.template` (replacing `{{VENV_PYTHON}}` and `{{PROJECT_DIR}}` with absolute paths)
4. Creates data directories

| | Standalone | Plugin |
|---|---|---|
| **Dependency manager** | pip (or uv with `--uv` flag) | uv (automatic) |
| **MCP config** | `.mcp.json` generated by `setup.sh` | `mcp-servers.plugin.json` via `plugin.json` |
| **Data directories** | Created by `setup.sh` | Created by `SessionStart` hook |
| **First-time setup** | ~2 min (manual, one-time) | ~30 sec (automatic, on first MCP call) |
| **Subsequent sessions** | Instant | Instant |

### What Happens When a User Installs the Plugin

Step by step:

1. **User adds the marketplace** (one-time):
   ```
   /plugin  →  Marketplaces tab  →  Add  →  hugoguerrap/crypto-claude-desk
   ```

2. **User installs the plugin**:
   ```
   /plugin  →  Discover tab  →  crypto-trading-desk  →  Install
   ```
   Claude Code clones the repo into `~/.claude/plugins/cache/crypto-trading-desk/`.

3. **User starts a new session**. The `SessionStart` hook fires and runs `post-setup.sh`, which creates `data/trades/`, `data/reports/`, and copies `portfolio.json.example` to `portfolio.json`. This takes ~10ms.

4. **User runs `/crypto-trading-desk:quick BTC`**. Claude Code invokes the `market-monitor` agent, which calls MCP tools. The first MCP call triggers `uv run`, which installs Python dependencies (~30 sec). After that, all MCP calls are instant.

5. **Everything works**. 6 agents, 4 skills, 66 MCP tools, all available.

### Plugin User Settings

After installing the plugin, add these to your Claude Code settings (`~/.claude/settings.json` or `.claude/settings.json` in your project) for the best experience:

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

Without these settings, Claude Code will prompt you to approve each MCP tool the first time it's used, and Agent Teams (needed for `/analyze`) won't be available.

### Local Plugin Development

To test changes without installing:

```bash
# Run Claude Code with the plugin loaded from a local directory
claude --plugin-dir /path/to/crypto-trading-desk

# Or load multiple plugins at once
claude --plugin-dir ./crypto-trading-desk --plugin-dir ./another-plugin
```

Skills will appear namespaced: `/crypto-trading-desk:quick`, `/crypto-trading-desk:analyze`, etc.

---

## Disclaimer

This is a **paper trading system only**. No real money is at risk. All trades are simulated in `data/trades/portfolio.json`.

This project is for educational and experimental purposes. It is not financial advice. Cryptocurrency markets are volatile and unpredictable. Do not use this system's outputs as the sole basis for real trading decisions.

---

## License

[MIT License](LICENSE) -- Copyright (c) 2025 Crypto Trading Desk Contributors
