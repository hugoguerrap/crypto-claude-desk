---
name: create
description: Extend the system by creating new MCP servers, agents, or skills. Usage: /create a DeFi protocol tracker or /create an agent for macro analysis
user-invocable: true
---

# Create New Component

Extend the crypto trading desk with a new component based on the user's natural language description: $ARGUMENTS

## Workflow

### Step 1: Parse Request
Determine what the user wants to create:
- **MCP server** — if the request involves new data sources, APIs, or tools (e.g., "on-chain analytics", "DeFi tracker", "social media monitor")
- **Agent** — if the request involves a new specialist role (e.g., "macro analyst", "DeFi strategist", "on-chain detective")
- **Skill** — if the request involves a new workflow or command (e.g., "multi-coin comparison", "rebalance portfolio", "alert system")

If unclear, ask the user what type of component they want.

### Step 2: Research
Delegate to `system-builder` agent:
"Research what's needed to create: $ARGUMENTS. Use WebSearch to find relevant public APIs (prefer no-API-key-required). Use WebFetch to read API documentation. Read existing components in the project to understand patterns — read at least 2 files from the relevant directory (mcp-servers/, agents/, or skills/). Read mcp-servers/validators.py for reusable validation. Write a research summary to data/create/{name}-research.md with: APIs found, rate limits, data available, recommended approach."

### Step 3: Generate
After research completes, delegate to `system-builder` agent:
"Based on the research in data/create/{name}-research.md, generate a new {type} for: $ARGUMENTS. Follow the exact patterns from existing files. Write the component to the correct location:
- MCP server → mcp-servers/{name}.py
- Agent → agents/{name}.md
- Skill → skills/{name}/SKILL.md
Write a creation summary to data/create/{name}-summary.md."

### Step 4: Integration Guidance
After the component is generated, present:

1. **What was created** — show the file path and a brief description
2. **Review** — show the key parts of the generated file for the user to review
3. **Next steps** — tell the user what they need to do:

For **MCP servers**:
- Add the server configuration to `mcp-servers.plugin.json`
- Add the server name to relevant agents' `mcpServers` list in their frontmatter
- Add the server to the MCP table in `CLAUDE.md`
- Run `/setup` to verify the new server starts correctly

For **agents**:
- Add routing rules in `CLAUDE.md` (which queries should route to this agent)
- Add the agent to the agents table in `CLAUDE.md`

For **skills**:
- Auto-discovered by Claude Code — no configuration needed
- Add to the skills table in `CLAUDE.md` for documentation

### Output
Present:
1. Research findings (APIs, feasibility)
2. Generated component (file path + key capabilities)
3. Integration checklist (numbered steps)
4. Suggested test command to verify it works
