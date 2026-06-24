# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an educational repository that teaches harness engineering -- building the environment that surrounds an AI agent model. It reverse-engineers Claude Code's architecture through 12 progressive sessions (s01-s12), demonstrating that **the model is the agent, the code is the harness**.

## Quick Start

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env  # Edit .env with your ANTHROPIC_API_KEY and MODEL_ID

# Run sessions sequentially
python agents/s01_agent_loop.py           # Start here: basic agent loop
python agents/s02_tool_use.py             # Tool dispatch pattern
python agents/s03_todo_write.py           # Planning system
python agents/s04_subagent.py             # Subagent isolation
python agents/s05_skill_loading.py        # On-demand knowledge loading
python agents/s06_context_compact.py      # Context compression strategy
python agents/s07_task_system.py          # Persistent task management
python agents/s08_background_tasks.py     # Async command execution
python agents/s09_agent_teams.py          # Team coordination basics
python agents/s10_team_protocols.py       # Team communication patterns
python agents/s11_autonomous_agents.py    # Self-managing agents
python agents/s12_worktree_task_isolation.py  # Full isolation + coordination
python agents/s_full.py                   # Capstone: all mechanisms combined

# Web platform (interactive learning)
cd web && npm install && npm run dev      # http://localhost:3000
```

## Core Architecture

### The Agent Loop Pattern

Every agent session builds on this fundamental pattern:

```python
def agent_loop(messages):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM,
            messages=messages, tools=TOOLS,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return

        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = TOOL_HANDLERS[block.name](**block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })
        messages.append({"role": "user", "content": results})
```

**Key principle**: The MODEL decides when to call tools and when to stop. The CODE just executes what the model asks for.

### Directory Structure

```
learn-claude-code/
├── agents/              # Python reference implementations (s01-s12 + s_full)
├── docs/{en,zh,ja}/     # Mental-model-first documentation (3 languages)
├── web/                 # Next.js interactive learning platform
├── skills/              # Skill files for s05 (agent-builder, code-review, mcp-builder, pdf)
├── tests/               # pytest-based tests
└── .github/workflows/   # CI for web platform
```

## Development Commands

### Python Agents

```bash
# Run a specific session
python agents/s01_agent_loop.py

# Test all agents compile
pytest tests/test_agents_smoke.py

# Run background tasks test
pytest tests/test_s_full_background.py
```

### Web Platform

```bash
cd web

# Install dependencies
npm install

# Development server
npm run dev

# Production build
npm run build

# Type check
npx tsc --noEmit

# Extract documentation content (runs automatically before dev/build)
npm run extract
```

## Architecture Principles

### Harness vs Agent

- **Agent**: The neural network (Claude, GPT, etc.) trained to perceive, reason, and act
- **Harness**: The code that gives the agent tools, knowledge, context, and permissions
- **Your role**: Build great harnesses. The agent will do the rest.

### Session Progression

Each session adds one harness mechanism without changing the core loop:

| Session | Mechanism | Key Concept |
|---------|-----------|-------------|
| s01 | Basic Loop | `while stop_reason == "tool_use"` |
| s02 | Tool Dispatch | `{name: handler}` dispatch map |
| s03 | Planning | List steps first, then execute |
| s04 | Subagents | Independent messages[] per child |
| s05 | Skills | Load knowledge via tool_result |
| s06 | Context Compression | 3-layer strategy for infinite sessions |
| s07 | Tasks | File-based CRUD + dependency graph |
| s08 | Background Tasks | Daemon threads + notify queue |
| s09 | Teams | Persistent teammates + JSONL mailboxes |
| s10 | Team Protocols | Request-response negotiation patterns |
| s11 | Autonomous Agents | Idle cycle + auto-claim |
| s12 | Worktree Isolation | Task coordination + optional isolated execution lanes |

### Task System

Tasks persist as JSON files in `.tasks/` to survive context compression:

```json
{
  "id": 1,
  "subject": "Fix authentication bug",
  "description": "Detailed requirements...",
  "status": "pending|in_progress|completed",
  "blockedBy": [2, 3],
  "blocks": [4, 5]
}
```

Dependency resolution: tasks can only start when `blockedBy` is empty.

### Skills System

Skills are loaded on-demand via tool_result injection, not upfront. Each skill directory contains:

- `SKILL.md`: Skill definition and instructions
- `references/`: Supporting documentation
- `scripts/`: Optional helper scripts

## Configuration

### Environment Variables

Required in `.env`:
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `MODEL_ID`: Model to use (e.g., `claude-sonnet-4-6`)

Optional:
- `ANTHROPIC_BASE_URL`: For Anthropic-compatible providers (MiniMax, GLM, Kimi, DeepSeek)

### Model Support

The project supports multiple Anthropic-compatible providers. See `.env.example` for configuration details.

## Testing Strategy

- **Compilation tests**: Ensure all Python agent scripts compile without errors
- **Background task tests**: Verify async command execution in s_full.py
- **CI**: Runs TypeScript compilation and build on the web platform

Run tests with `pytest`.

## Documentation Approach

Mental-model-first: problem, solution, ASCII diagram, minimal code. Available in English, Chinese, and Japanese.

Each session documentation follows this pattern:
1. The problem being solved
2. The solution approach
3. ASCII diagram of the mechanism
4. Minimal implementation code
5. Usage examples

## Code Conventions

- Python: Docstrings for all functions, clear variable names, modular design
- Sessions build progressively: later sessions import concepts from earlier ones
- No external dependencies beyond `anthropic`, `python-dotenv`, and `pyyaml`
- Web platform: Next.js 16, React 19, TypeScript 5, Tailwind CSS 4

## Scope Limitations

This is a 0->1 learning project that intentionally simplifies production mechanisms:
- Minimal event/hook system in s12 (not a full event bus)
- Basic permission governance (not rule-based trust workflows)
- Simplified session lifecycle controls
- Teaching implementation of team JSONL protocol (not production internals)

## Related Projects

- **Kode CLI**: Open-source coding agent CLI with skill & LSP support
- **Kode SDK**: Embed agent capabilities in your app without per-user process overhead
- **OpenClaw/Claw0**: Always-on assistant harness (heartbeat + cron + IM routing)
