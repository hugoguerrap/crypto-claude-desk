# Contributing to Crypto Trading Desk

Thank you for your interest in contributing. This guide covers how to report bugs, propose features, and submit changes.

---

## Reporting Bugs

Open a GitHub issue with the following information:

1. **What happened.** Describe the unexpected behavior.
2. **What you expected.** Describe the correct behavior.
3. **Steps to reproduce.** Include the exact command or query (e.g., `/analyze BTC`).
4. **Environment.** Your OS, Python version, Claude Code version, and whether you modified any agent or MCP server files.
5. **Error output.** If an MCP server failed, include the error message. If an agent produced incorrect output, paste the relevant section.

For agent-specific issues, note which agent was involved (check `data/reports/` for individual agent outputs during full analyses).

---

## Proposing Features

Open a GitHub issue labeled `enhancement` with:

1. **Problem statement.** What limitation are you trying to address?
2. **Proposed solution.** How would you implement it?
3. **Affected components.** Which agents, MCP servers, skills, or routing rules would change?
4. **Alternatives considered.** What other approaches did you evaluate?

---

## Submitting Changes

### Workflow

1. Fork the repository.
2. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Make your changes.
4. Test your changes (see Testing below).
5. Commit with a clear message describing the change.
6. Open a pull request against `main`.

### Pull Request Guidelines

- Keep PRs focused. One feature or fix per PR.
- Update `CLAUDE.md` if you change routing rules, add agents, or add MCP servers.
- Update `docs/` if your change affects architecture, extension guides, or configuration.
- Include a brief description of what changed and why.
- If you added a new MCP tool, include example output showing it works.

---

## Code Style

### Python (MCP Servers)

- **Language:** All code in English. Variable names, function names, and comments in English.
- **Type hints:** Use type hints for all function parameters and return values.
- **Docstrings:** Every `@mcp.tool()` function must have a docstring with `Args` and `Returns` sections. These docstrings are surfaced to the AI agents, so clarity matters.
- **Error handling:** Every tool must wrap its logic in try/except and return `{"error": str(e), "status": "error"}` on failure. Never let an exception propagate uncaught.
- **Logging:** Use the `logging` module for diagnostic output. Do not use `print()`.
- **Input validation:** Validate parameters early. Return a clear error if an exchange name is not in the `EXCHANGES` dictionary or a symbol format is invalid.
- **No emojis in code.** Emojis are acceptable only in user-facing interpretation strings (e.g., the `interpretation` field in a tool's return value). Do not use them in variable names, comments, docstrings, or log messages.
- **Dependencies:** Minimize external dependencies. Prefer CCXT + standard library where possible. If you need a new package, document it.

### Agent Files (agents/)

- Write clear, specific instructions. Agents perform better with concrete steps than vague guidance.
- Include a "Parallel Execution" section if the agent should call multiple MCP tools simultaneously.
- Include an "Output Format" section defining the structure of the agent's report.
- Always set `disallowedTools` to restrict access following the principle of least privilege.

### Skill Files (skills/)

- Keep skill workflows sequential and explicit. Number each step.
- Reference specific agent names and file paths.
- Include timeout rules for long-running operations.

### CLAUDE.md

- Use tables for structured information (agent lists, MCP server lists, routing rules).
- Keep routing rules unambiguous. The coordinator should never be uncertain about which path to take.
- Bold important rules (e.g., **ALWAYS**, **NEVER**, **IMPORTANT**).

---

## Testing

There is no automated test suite. This project relies on manual smoke testing through Claude Code.

### Smoke Test Checklist

Before submitting a PR, verify:

1. **Quick query works:**
   ```
   /quick BTC
   ```
   Confirm: market-monitor returns price, volume, Fear & Greed, funding rate.

2. **MCP servers respond:**
   Ask Claude Code to call a tool from the MCP server you modified. Verify it returns valid data (not an error).

3. **Agent routing is correct:**
   Ask a natural language question that should route to your new/modified agent. Verify the correct agent handles it.

4. **Report files are written (for full analysis):**
   After running `/analyze BTC`, check that all expected files exist in `data/reports/YYYY-MM-DD-BTC/`.

5. **Portfolio operations work (if you changed portfolio-manager):**
   Run `/portfolio` and verify it reads `data/trades/portfolio.json` correctly.

### Prototyping with /create

The fastest way to prototype a new component is with the `/create` skill:
```
/create an MCP server for on-chain analytics
/create an agent for macro economic analysis
/create a skill for multi-coin comparison
```
The system-builder agent will research APIs, read existing patterns, and generate the component for you. Review the output, then integrate it following the steps above.

### Testing a New MCP Server

You can test a new MCP server in isolation before integrating it:

```bash
# Run the server directly
uv run --project . python mcp-servers/your_server.py

# Or test individual functions in a Python shell
uv run --project . python -c "
from mcp_servers.your_server import your_tool_name
result = your_tool_name('BTC')
print(result)
"
```

---

## Project Structure

```
crypto-trading-desk/
    .claude-plugin/
        plugin.json                    # Plugin manifest
        marketplace.json               # Marketplace definition
    agents/                            # 7 agent definitions (auto-discovered)
        market-monitor.md
        technical-analyst.md
        news-sentiment.md
        risk-specialist.md
        portfolio-manager.md
        learning-agent.md
        system-builder.md
    skills/                            # 7 slash commands (auto-discovered)
        analyze/SKILL.md
        quick/SKILL.md
        portfolio/SKILL.md
        close-trade/SKILL.md
        validate-predictions/SKILL.md
        create/SKILL.md
        setup/SKILL.md
    hooks/
        hooks.json                     # SessionStart hook
        post-setup.sh                  # Creates data dirs (~10ms)
    mcp-servers/                       # 6 Python MCP servers (65 tools)
        crypto_ultra_simple.py
        crypto_exchange_ccxt_ultra.py
        crypto_technical_analysis.py
        crypto_futures_data.py
        crypto_advanced_indicators.py
        crypto_market_microstructure.py
    mcp-servers.plugin.json            # MCP config (uv run + ${CLAUDE_PLUGIN_ROOT})
    pyproject.toml                     # Python dependencies (for uv)
    CLAUDE.md                          # Coordinator instructions and routing rules
    README.md                          # Project overview
    CONTRIBUTING.md                    # This file
    LICENSE                            # MIT license
    data/
        trades/portfolio.json.example           # Example portfolio
        trades/predictions.json.example         # Prediction tracking template
        trades/agent-scorecards.json.example    # Agent accuracy scorecards
        trades/patterns.json.example            # Pattern library template
        reports/                                # Agent analysis reports
        logs/                                   # Operational logs
        create/                                 # /create research artifacts
    docs/
        architecture.md                # Technical deep-dive
        extending.md                   # How to extend the system
```

---

## Questions?

Open a GitHub issue with the `question` label.
