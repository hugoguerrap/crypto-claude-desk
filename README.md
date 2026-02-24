# Crypto Trading Desk

> *I used to spend weeks building multi-agent systems with LangGraph, CrewAI, and AutoGen. Hundreds of lines of Python orchestration code, custom state machines, fragile message passing between agents. Then I realized Claude Code already has everything — subagents, MCP servers, persistent memory, model routing. I just needed to describe my agents in markdown and give them tools. This plugin is the result: 7 coordinated AI agents, 83 real-time tools, zero lines of orchestration code. It even learns from its own trades and can extend itself.*
>
> — [Hugo Guerra](https://github.com/hugoguerrap)

---

**Claude Code is not just for writing code.** Its agent system is a general-purpose intelligence platform. You can point it at any domain, give it specialized tools, and let it coordinate expert agents to solve problems that would take a human team hours.

This project proves it. One plugin turns Claude Code into a full crypto trading desk — and it's built entirely with markdown files and MCP servers. No framework. No SDK. No middleware.

**It's markdown all the way down.**

---

## Install

### Option A: As a plugin (recommended for users)

```bash
# 1. Add the marketplace
claude plugin marketplace add hugoguerrap/crypto-claude-desk

# 2. Install the plugin
claude plugin install crypto-trading-desk@hugoguerrap

# 3. Start Claude Code
claude
```

### Option B: From source (recommended for contributors)

```bash
# 1. Clone the repo
git clone https://github.com/hugoguerrap/crypto-trading-desk.git
cd crypto-trading-desk

# 2. Start Claude Code with the plugin directory
claude --plugin-dir .
```

Both modes auto-discover agents, skills, and MCP servers. Same code, same behavior.

Then run setup once:

```
/crypto-trading-desk:setup
```

Setup detects your OS (macOS, Linux, or Windows), installs [uv](https://docs.astral.sh/uv/) if missing, downloads Python dependencies, verifies all 7 MCP servers work, and reports status. Takes ~30 seconds. You only need to do this once.

### First thing to try

```
/crypto-trading-desk:quick BTC
```

Live market snapshot in ~15 seconds: price, volume, Fear & Greed, funding rates, whale activity.

---

## What you can do

### Slash commands

| Command | What it does | Time |
|---------|-------------|------|
| `/crypto-trading-desk:setup` | First-time setup (detects OS, installs deps, verifies) | ~30 sec |
| `/crypto-trading-desk:quick BTC` | Live market snapshot (1 agent) | ~15 sec |
| `/crypto-trading-desk:analyze ETH` | Full 5-agent phased analysis with trading decision | ~3-5 min |
| `/crypto-trading-desk:portfolio` | View balances, open trades, P&L | ~30 sec |
| `/crypto-trading-desk:close-trade trade_001` | Close a trade + post-mortem + learning | ~1 min |
| `/crypto-trading-desk:validate-predictions` | Review predictions against market data | ~30 sec |
| `/crypto-trading-desk:monitor` | Autonomous loop: check SL/TP, close trades, evaluate, summarize | ~2-3 min |
| `/crypto-trading-desk:create` | Extend the system with new components | ~2-3 min |

### Natural language

Just ask naturally. The system routes to the right agent(s) based on complexity:

| You say | What happens |
|---------|-------------|
| "How's BTC?" | 1 agent (market-monitor) checks price, volume, sentiment |
| "RSI of ETH?" | 1 agent (technical-analyst) calculates indicators |
| "What's the news on SOL?" | 1 agent (news-sentiment) scans web + social media |
| "Analyze LINK" | 3 agents in parallel: market + technical + news |
| "Should I buy BTC? Full analysis" | 5-agent team with phased execution and final decision |
| "Check my portfolio" | Portfolio manager reviews positions and P&L |
| "Check my predictions" | Learning agent validates predictions against current prices |
| "Create a DeFi tracker" | System builder researches APIs and generates the component |

---

## How it works

### The 7 agents

Each agent is a specialist with its own model tier, tools, and instructions:

| Agent | Role | Model | What it uses |
|-------|------|-------|-------------|
| **market-monitor** | Live prices, volume, funding rates, whale alerts | Haiku (fast, cheap) | 5 exchanges via CCXT, CoinGecko, web search |
| **technical-analyst** | RSI, MACD, Bollinger, Ichimoku, patterns, signals | Sonnet | 38 technical indicators |
| **news-sentiment** | Breaking news, social mood, FUD/FOMO detection | Sonnet | Web search + web fetch (Claude's native NLP) |
| **risk-specialist** | Volatility, VaR, orderbook depth, spoofing detection | Sonnet | Microstructure analysis, correlation |
| **portfolio-manager** | Final EXECUTE/WAIT/REJECT decision, paper trading | Opus (smartest) | Reads all reports, manages portfolio state |
| **learning-agent** | Predictions, patterns, post-mortem | Opus | Tracks accuracy, evaluates setups, builds patterns |
| **system-builder** | Generate new MCP servers, agents, skills + tests | Opus | Researches APIs, reads existing patterns, generates code + tests |

Using Haiku for data scouts and Opus only for final decisions saves ~40-60% on tokens compared to running everything on one model.

### Full analysis flow (`/analyze`)

When you request a full analysis, 5 agents coordinate in phases:

```
Phase 1 (parallel, ~60 sec)
  market-monitor ---------> market-data.md
  technical-analyst ------> technical-analysis.md
  news-sentiment ---------> news-sentiment.md
         |
         v (waits for Phase 1)
Phase 2 (~60 sec)
  risk-specialist --------> risk-assessment.md
         |
         v (waits for Phase 2)
Phase 3 (~60 sec)
  portfolio-manager ------> decision.md
         |
         v
  EXECUTE / WAIT / REJECT
  with entry, SL, TP, position size, R:R ratio
```

Each agent writes a report file. The next phase reads those files. No message passing — just files on disk.

### 83 MCP tools across 7 servers

| Server | Tools | What it provides |
|--------|-------|-----------------|
| crypto-data | 11 | Fear & Greed, dominance, rankings, categories (CoinGecko) |
| crypto-exchange | 16 | Live prices, orderbooks, OHLCV, volume, arbitrage (5 exchanges via CCXT) |
| crypto-technical | 14 | RSI, MACD, Bollinger, patterns, signals, backtesting |
| crypto-futures | 10 | Funding rates, open interest, long/short ratios, liquidation levels |
| crypto-advanced-indicators | 8 | OBV, MFI, ADX, Ichimoku, VWAP, Pivot Points, divergences |
| crypto-market-microstructure | 6 | Orderbook depth, imbalance, spread, spoofing, market impact |
| crypto-learning-db | 18 | Trade CRUD, predictions, track records, patterns, summaries, trade modifications (SQLite) |

All powered by public APIs. **No API keys required.**

### Paper trading

The portfolio manager executes trades in a local SQLite database (`data/db/learning.db`) via the crypto-learning-db MCP. No real money. You start with $10,000 spot + $10,000 futures. Every trade has mandatory stop-loss, minimum 2:1 risk/reward, and position limits.

### Cognitive learning

The system gets smarter with every trade:

1. **Predictions tracked** — When a trade opens, every agent's testable prediction is recorded (price targets, support levels, funding expectations)
2. **Evaluated in natural language** — When the trade closes, the learning agent reads original predictions vs actual outcomes and writes a detailed NL evaluation: what worked, what failed, why, and what we can learn. No formulas — just reasoning stored for future reference.
3. **Setup-centric track records** — `get_prediction_track_record()` provides accuracy by time window (7d, 30d, 90d, global) plus NL evaluations, filtered by setup type, symbol, and agent. The portfolio manager asks "how has this type of setup performed?" not "do I trust this agent?"
4. **Expired prediction detection** — Predictions past their timeframe are automatically surfaced with market context so the learning agent can batch-evaluate them
5. **Pattern library** — Named trading setups (e.g., "oversold bounce at support") with tracked win rates. Patterns above 60% are marked SEEK; below 40% are marked AVOID
6. **Claude is the consensus engine** — No weighted formulas, no confidence_adjustment math. The portfolio manager reads setup track records, evaluations, and agent reasoning, then decides through natural language analysis how reliable each signal is for this specific trade

Run `/validate-predictions` anytime to check pending predictions against current market data.

### Self-evolving platform

The `/create` skill lets you extend the system in natural language:

```
/create an MCP server for on-chain analytics
/create an agent for macro economic analysis
/create a skill for multi-coin comparison
```

The system-builder agent (opus) researches APIs, reads existing components for patterns, generates the new component, and tells you what integration steps remain. The system grows with your needs.

### Autopilot mode

Claude Code's `-p` flag runs headless (no interaction needed). Combine it with cron and the system becomes an autonomous analyst.

**Important:** Cron runs without a terminal, so you need `--allowedTools` to pre-approve tool permissions. You also need the correct working directory so Claude Code finds `CLAUDE.md` and the plugin configuration.

```bash
# Use the wrapper script for proper environment setup
# Monitor every hour: check SL/TP, close trades, evaluate expired predictions
0 * * * * /path/to/crypto-trading-desk/bin/autopilot.sh monitor

# Morning market briefing at 8am
0 8 * * * /path/to/crypto-trading-desk/bin/autopilot.sh quick "BTC ETH SOL"

# Full analysis every Monday at 9am
0 9 * * 1 /path/to/crypto-trading-desk/bin/autopilot.sh analyze "BTC"

# Portfolio check at US market close
0 16 * * 1-5 /path/to/crypto-trading-desk/bin/autopilot.sh portfolio
```

**Why a wrapper?** Skills (`/skill-name`) are not invoked in `-p` mode. The wrapper maps workflow names to detailed natural language prompts, handles PATH/env for cron, pre-approves tool permissions with `--allowedTools`, auto-detects `--plugin-dir` (works for both plugin install and local clone), and logs output to `data/logs/`.

**Adding custom workflows:** Edit `bin/autopilot.sh` and add a new `case` block. Each workflow is just a natural language prompt — describe what you want Claude to do using the agents and MCP tools available.

The `monitor` workflow closes the autonomous loop: it checks open trades against SL/TP levels, closes trades that hit targets, triggers post-mortem analysis with NL evaluations, validates expired predictions, and generates monthly summaries. Combined with `analyze` for trade entries, the system runs a complete learn-trade-evaluate cycle without human intervention.

---

## The old way vs. this way

| | Traditional multi-agent frameworks | This plugin |
|---|---|---|
| **Orchestration** | Python code (LangGraph, CrewAI, AutoGen) | `CLAUDE.md` — plain English routing rules |
| **Agent definitions** | Python classes, decorators, schemas | Markdown files with YAML frontmatter |
| **Tool integration** | Custom wrappers, API clients, SDKs | MCP servers (standard protocol) |
| **Coordination** | State machines, graphs, message queues | File-based — agents write reports, next phase reads them |
| **Memory** | Vector databases, custom storage | Built-in `memory: project` (one line in agent config) |
| **Model routing** | Custom logic per agent | `model: haiku` / `sonnet` / `opus` in frontmatter |
| **Setup time** | Days to weeks | Hours. Describe agents, build MCP tools, write CLAUDE.md |
| **Lines of orchestration code** | Hundreds to thousands | **Zero** |

---

## Requirements

| Requirement | How it's handled |
|-------------|-----------------|
| **Claude Code** | [Install guide](https://docs.anthropic.com/en/docs/claude-code) — you need a Claude Pro/Max/Team plan |
| **Python 3.11+** | Most systems have it. `uv` downloads it automatically if missing |
| **uv** | `/setup` installs it automatically. Or install manually: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
### Recommended settings

Add to `~/.claude/settings.json` for the smoothest experience:

```json
{
  "permissions": {
    "allow": [
      "mcp__crypto-data",
      "mcp__crypto-exchange",
      "mcp__crypto-technical",
      "mcp__crypto-futures",
      "mcp__crypto-advanced-indicators",
      "mcp__crypto-market-microstructure",
      "mcp__crypto-learning-db",
      "WebSearch",
      "WebFetch",
      "Write"
    ]
  }
}
```

Without this, Claude Code will ask you to approve each tool on first use (which works fine, just slower).

---

## Troubleshooting

**First step for any issue:** run `/crypto-trading-desk:setup`. It detects problems and fixes them automatically.

### MCP servers not starting

**"spawn uv ENOENT"** — `uv` is installed but Claude Code can't find it. Common when launching from GUI apps (Claude Desktop, VS Code) that don't inherit your terminal's PATH.

Fix:
```bash
# Create a symlink so GUI apps can find uv
sudo ln -sf ~/.local/bin/uv /usr/local/bin/uv
# Then restart Claude Code
```

Or just run `/crypto-trading-desk:setup` — it detects this and offers to fix it.

### Dependencies not installing

```bash
cd ~/.claude/plugins/cache/crypto-trading-desk  # or your local clone
uv sync
```

### Windows users

The plugin works on Windows. Run `/crypto-trading-desk:setup` — it detects Windows and uses PowerShell to install `uv` if needed. If you get PATH issues, ensure `uv` is in your system PATH or install it via `winget install astral-sh.uv`.

---

## Architecture

```
crypto-trading-desk/
├── agents/                      # 7 agent definitions (Markdown + YAML frontmatter)
├── bin/                         # autopilot.sh wrapper for cron/headless execution
├── skills/                      # 8 slash commands (setup, quick, analyze, portfolio, close-trade, validate-predictions, monitor, create)
├── hooks/                       # SessionStart: creates data directories
├── mcp-servers/                 # 7 Python MCP servers (83 tools total)
├── mcp-servers.plugin.json      # MCP config for plugin distribution
├── pyproject.toml               # Python dependencies (pinned in uv.lock)
├── uv.lock                      # Reproducible dependency resolution
├── .python-version              # Pins Python 3.12
├── CLAUDE.md                    # Routing logic — Claude Code reads this to coordinate
└── data/
    ├── db/learning.db           # SQLite cognitive memory (trades, predictions, patterns)
    ├── reports/                 # Analysis reports (one folder per analysis)
    └── create/                  # /create research artifacts
```

**Zero orchestration code.** Claude Code reads `CLAUDE.md` and coordinates everything. The agents are markdown files. The skills are markdown files. The routing logic is markdown.

---

## Build your own

This project is a template. The architecture — agents as markdown, tools as MCP servers, coordination as CLAUDE.md — works for any domain:

- **Security research**: agents for CVE scanning, exploit analysis, patch verification
- **Competitive intelligence**: agents for pricing, feature tracking, sentiment monitoring
- **Operations**: agents for log analysis, incident triage, runbook execution
- **Financial analysis**: agents for fundamentals, technicals, macro, portfolio optimization

To build your own multi-agent system on Claude Code:

1. Define your agents in `agents/` (markdown + YAML frontmatter)
2. Build your data sources as MCP servers in `mcp-servers/`
3. Write routing logic in `CLAUDE.md`
4. Add user commands in `skills/`

See [docs/extending.md](docs/extending.md) for the full guide.

---

## Contributing

This is an open project. Add new agents, MCP servers, skills, or improve existing ones.

- **New MCP server** — add a data source (on-chain analytics, DEX data, social metrics)
- **New agent** — add a specialist (macro analyst, on-chain detective, DeFi strategist)
- **New skill** — add a workflow (multi-coin comparison, portfolio rebalancing, alert system)
- **Improve existing agents** — better prompts, smarter routing, new analysis patterns

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. PRs welcome.

---

## Disclaimer

This is a **paper trading system** for educational and experimental purposes. No real money is at risk. All trades are simulated. This is not financial advice.

---

## License

[MIT](LICENSE)

Built by [Hugo Guerra](https://github.com/hugoguerrap)
