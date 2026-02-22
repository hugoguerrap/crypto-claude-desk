---
name: setup
description: First-time setup for Crypto Trading Desk. Detects your environment, installs dependencies, and verifies everything works. Run this once after installing the plugin.
user-invocable: true
---

# Crypto Trading Desk - Setup

Run environment detection and dependency setup. This skill makes the plugin work on any platform.

## Workflow

### Step 1: Detect Environment
Run these checks in parallel using Bash:
- `uname -s` (or `ver` on Windows) to detect OS
- `python3 --version` or `python --version` to check Python
- `which uv` or `where uv` to check if uv is installed
- Check if `.venv` directory exists in the plugin root
- Check if `data/trades/portfolio.json` exists

### Step 2: Install uv (if missing)
Based on detected OS:

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installing, verify `uv` is accessible. If it's installed to `~/.local/bin/` but not in PATH (common on macOS GUI apps), offer to create a symlink:
```bash
sudo ln -sf ~/.local/bin/uv /usr/local/bin/uv
```

If the user declines sudo, tell them to restart their terminal and try again.

### Step 3: Install Python dependencies
```bash
uv sync --project <plugin_root>
```
This creates `.venv/` and installs all packages from `uv.lock` (fastmcp, ccxt, numpy, pandas, requests).

If `uv sync` fails, try without `--frozen`:
```bash
uv sync --project <plugin_root>
```

### Step 4: Create data directories
```bash
mkdir -p data/trades data/reports data/logs .claude/agent-memory/portfolio-manager
```

If `data/trades/portfolio.json` doesn't exist, copy from `data/trades/portfolio.json.example`.

### Step 5: Verify MCP servers work
Test that one MCP server can start by running:
```bash
uv run --frozen --project <plugin_root> python -c "import fastmcp; import ccxt; import numpy; import pandas; print('OK')"
```

If this fails, diagnose and fix. Common issues:
- Python version too old → tell user to install Python 3.11+
- Missing system dependencies → platform-specific guidance

### Step 6: Check recommended settings
Read `~/.claude/settings.json` and check if:
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is set to `"1"`
- MCP tool permissions are allowed

If not, show the user what to add and offer to configure it.

### Step 7: Report
Present a clear status report:

```
Crypto Trading Desk - Setup Complete

  OS:           macOS 15.3 (arm64)
  Python:       3.12.8
  uv:           0.6.13
  Dependencies: 5/5 installed
  MCP Servers:  6/6 ready
  Data dirs:    Created
  Portfolio:    Initialized ($20,000 paper trading)
  Agent Teams:  Enabled / Not enabled (add to settings.json)

  Ready to use:
    /crypto-trading-desk:quick BTC     (fast market check)
    /crypto-trading-desk:analyze ETH   (full 5-agent analysis)
```

If anything failed, show exactly what went wrong and how to fix it.
