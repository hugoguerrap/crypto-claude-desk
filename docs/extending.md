# Extending the System

This guide covers how to add new agents, MCP servers, skills, exchanges, and routing rules to the Crypto Trading Desk.

---

## Quick Start: Using /create

The fastest way to extend the system is the `/create` skill:

```
/create an MCP server for on-chain analytics using public blockchain APIs
/create an agent for macro economic analysis
/create a skill for multi-coin comparison
```

The system-builder agent (opus) will:
1. Research relevant APIs via WebSearch
2. Read existing components to match patterns
3. Generate the new component
4. Tell you what integration steps remain

This is the recommended way to prototype new components. For production-quality additions, review the generated code and refine it using the manual instructions below.

---

## Adding a New Agent

Agents are Markdown files in `agents/`. To add a new agent:

### 1. Create the agent file

Create `agents/your-agent-name.md` with YAML frontmatter and a system prompt.

```markdown
---
name: your-agent-name
description: When to use this agent (the coordinator reads this to decide routing).
model: sonnet
mcpServers:
  - crypto-data
  - crypto-exchange
tools: WebSearch, Read, Write
disallowedTools: Edit
maxTurns: 12
---

# Your Agent Name - Role Description

You are the **Your Agent**, specialized in [what it does].

## Analysis Framework

[Step-by-step instructions for what this agent should do]

## Output Format

[How the agent should format its output]
```

### 2. Choose the right model

| Model | Use When | Cost |
|---|---|---|
| haiku | Data gathering, pattern lookup, simple tasks | Low |
| sonnet | Analysis, reasoning, synthesis | Medium |
| opus | High-stakes decisions requiring the best judgment | High |

### 3. Configure tool access

Follow the principle of least privilege:

- Only list the MCP servers the agent actually needs in `mcpServers`.
- Only list native tools it needs in `tools` (choices: `Read`, `Write`, `Grep`, `WebSearch`, `WebFetch`).
- Block tools it should not have in `disallowedTools` (typically `Edit` for agents that write report files).

### 4. Add persistent memory (optional)

If the agent should accumulate knowledge across sessions, add `memory: project` to the frontmatter. Use this sparingly -- only for agents that genuinely benefit from long-term memory (like the portfolio-manager and learning-agent).

### 5. Update CLAUDE.md

Add the new agent to the agents table in `CLAUDE.md` and update the routing rules to specify when the coordinator should delegate to it.

---

## Adding a New MCP Server

MCP servers are Python files in `mcp-servers/` using FastMCP.

### 1. Create the server file

Create `mcp-servers/your_server_name.py`:

```python
#!/usr/bin/env python3
"""
Your Server Name MCP Server
Description of what this server provides.
"""

from fastmcp import FastMCP
from typing import Dict, Any

mcp = FastMCP("your-server-name")


@mcp.tool()
def your_tool_name(param1: str = "default", param2: int = 10) -> Dict[str, Any]:
    """
    Description of what this tool does.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Dictionary with results
    """
    try:
        # Your implementation here
        result = {"data": "your data"}

        return {
            "result": result,
            "status": "success"
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error"
        }


if __name__ == "__main__":
    mcp.run()
```

### 2. Add to mcp-servers.plugin.json

Add your server to `mcp-servers.plugin.json`:

```json
{
  "mcpServers": {
    "your-server-name": {
      "command": "uv",
      "args": ["run", "--project", "${CLAUDE_PLUGIN_ROOT}", "python", "${CLAUDE_PLUGIN_ROOT}/mcp-servers/your_server_name.py"],
      "cwd": "${CLAUDE_PLUGIN_ROOT}"
    }
  }
}
```

### 3. Add permissions

Users should add the server to their `~/.claude/settings.json` permissions:

```json
{
  "permissions": {
    "allow": [
      "mcp__your-server-name"
    ]
  }
}
```

### 5. Assign to agents

Add the server name to the `mcpServers` list in any agent files that should use it.

### 6. Install dependencies

If your server requires additional Python packages, add them to `pyproject.toml`:

```toml
dependencies = [
    "your-package>=1.0,<2.0",
]
```

The `uv run --project` command will automatically install new dependencies on the next MCP call.

---

## Adding a New Skill

Skills are user-invocable slash commands defined in `skills/`.

### 1. Create the skill directory and file

```bash
mkdir -p skills/your-skill
```

Create `skills/your-skill/SKILL.md`:

```markdown
---
name: your-skill
description: What this skill does. Usage: /your-skill ARG
user-invocable: true
---

# Your Skill Name

Brief description. $ARGUMENTS contains whatever the user typed after the command.

## Workflow

1. Step one: delegate to agent X with specific prompt
2. Step two: process the result
3. Step three: present output to user

## Output

Describe what the user should see.
```

### 2. Reference $ARGUMENTS

The variable `$ARGUMENTS` is replaced with whatever the user types after the slash command. For example, if the user types `/your-skill BTC ETH`, then `$ARGUMENTS` becomes `BTC ETH`.

### 3. Design the workflow

A skill is essentially a recipe for the coordinator. It can:

- Delegate to one or more agents via the Task tool.
- Create an Agent Team for complex multi-agent workflows.
- Read and write files.
- Combine outputs from multiple agents.

---

## Modifying Routing Rules

All routing logic lives in `CLAUDE.md`. The coordinator reads this file at the start of every conversation.

### To change when a query goes to a specific agent:

Edit the "Routing Rules" section in `CLAUDE.md`. The tables define which query patterns map to which agents.

### To change the threshold between Quick/Standard/Full:

Edit the natural language descriptions in CLAUDE.md:

- **Quick:** "simple data points" -- price, single indicator, news check.
- **Standard:** "analyze X" without explicitly requesting a recommendation.
- **Full:** "full analysis", "should I buy", "recommendation", or `/analyze`.

### To add a new routing path:

Add a new entry to the "Special Queries" section or modify the routing tables. The coordinator uses these instructions to classify incoming queries.

---

## Adding Exchange Support

The CCXT-based MCP servers use a shared `EXCHANGES` dictionary.

### 1. Choose the exchange

CCXT supports hundreds of exchanges. Check the [CCXT documentation](https://docs.ccxt.com/) for the exchange ID.

Requirements for a public-API-only setup (no API keys):

- Must support `fetchTicker` (for prices).
- Must support `fetchOrderBook` (for liquidity data).
- Must support `fetchOHLCV` (for candlestick data).
- Must have reasonable response times (under 2 seconds).
- Must not require authentication for public endpoints.

### 2. Add to the EXCHANGES dictionary

In the relevant MCP server file(s), add the exchange to the `EXCHANGES` dictionary:

```python
EXCHANGES = {
    'binance': ccxt.binance(),
    'kraken': ccxt.kraken(),
    'your_exchange': ccxt.your_exchange(),  # Add here
}
```

### 3. Test the exchange

Before committing, verify the exchange works:

```python
import ccxt

exchange = ccxt.your_exchange()
exchange.sandbox = False

# Test basic operations
ticker = exchange.fetch_ticker('BTC/USDT')
print(f"Price: {ticker['last']}")

orderbook = exchange.fetch_order_book('BTC/USDT', 10)
print(f"Bids: {len(orderbook['bids'])}, Asks: {len(orderbook['asks'])}")

ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=10)
print(f"Candles: {len(ohlcv)}")
```

### 4. Update across all servers

If you want the exchange available everywhere, add it to:

- `mcp-servers/crypto_exchange_ccxt_ultra.py` -- for price, volume, and orderbook data.
- `mcp-servers/crypto_technical_analysis.py` -- for OHLCV data used in indicators.
- `mcp-servers/crypto_futures_data.py` -- only if the exchange supports futures.
- `mcp-servers/crypto_advanced_indicators.py` -- for advanced indicator calculations.
- `mcp-servers/crypto_market_microstructure.py` -- for microstructure analysis.

### 5. Note on problematic exchanges

Some exchanges have been tested and removed due to issues:

- **Coinbase:** `fetchStatus()` not supported, NoneType errors.
- **Bybit (spot):** `fetchStatus()` not supported (works for futures only).
- **Huobi:** API errors.
- **Gate.io:** `fetchStatus()` not supported.
- **OKX (spot):** Very slow response times (49+ seconds).

If you encounter similar issues, document them in the `EXCHANGES` dictionary comments and remove the exchange.
