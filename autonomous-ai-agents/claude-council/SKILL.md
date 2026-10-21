---
name: claude-council
description: Consult multiple AI models in parallel and cross-check.
version: 1.0.0
author: hex, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [claude-council, multi-agent, cross-check, llm-council, coding-agents]
    related_skills: [claude-code, codex, hermes-agent]
---

# Claude Council — Multi-Model AI Consensus & Cross-Checking

Claude Council runs queries across multiple AI models and coding agents in parallel, returning side-by-side answers and a synthesis comparing consensus and divergences.

Local repo path: `C:\Users\User\claude-council` (MSYS: `/c/Users/User/claude-council`)

## When to Use

- Cross-checking high-stakes architecture, database schema, or security decisions across models.
- Resolving tricky debugging dead-ends where a single model's bias might mislead.
- Evaluating trade-offs across Gemini, OpenAI, Grok, Perplexity, Kimi, and local models.

## Prerequisites

- **Repository**: Cloned at `C:\Users\User\claude-council`.
- **jq**: Installed (required for JSON parsing).
- **Environment**: Set API keys or CLI agents in your environment:
  - `OPENAI_API_KEY` (or `codex` CLI)
  - `GEMINI_API_KEY` (or `agy` / Antigravity CLI)
  - `XAI_API_KEY` (or `grok` CLI)
  - `PERPLEXITY_API_KEY`
  - `KIMI_API_KEY`
  - `OPENROUTER_API_KEY`
  - `OLLAMA_MODEL` / local Ollama

## Quick Reference Commands

Run all commands from `/c/Users/User/claude-council` via bash in the `terminal` tool:

```bash
# Check provider availability and credentials
cd /c/Users/User/claude-council && bash scripts/check-status.sh

# Query available providers
cd /c/Users/User/claude-council && bash scripts/query-council.sh -- "Your question here"

# Query specific providers
cd /c/Users/User/claude-council && bash scripts/query-council.sh --providers=gemini,openai -- "Your question"

# Assign specialized perspectives / roles
cd /c/Users/User/claude-council && bash scripts/query-council.sh --roles=balanced -- "Your question"

# Enable two-round debate mode
cd /c/Users/User/claude-council && bash scripts/query-council.sh --debate -- "Your question"

# Include a source file in query context
cd /c/Users/User/claude-council && bash scripts/query-council.sh --file=/path/to/file -- "Review this code"

# Human-readable output formatting
cd /c/Users/User/claude-council && bash scripts/query-council.sh --providers=gemini,openai -- "Question" 2>/dev/null | bash scripts/format-output.sh
```

## Available Roles

- `security` - Security Auditor (vulnerabilities, OWASP)
- `performance` - Performance Optimizer (efficiency, bottlenecks)
- `maintainability` - Maintainability Advocate (clarity, design)
- `devil` - Devil's Advocate (challenges assumptions)
- `simplicity` - Simplicity Champion (prevents over-engineering)
- `scalability` - Scalability Architect (distributed systems, growth)
- Presets: `balanced`, `security-focused`, `architecture`, `review`

## Pitfalls

- Always put `--` before the prompt argument to prevent flags misparsing.
- Ensure `jq` is on PATH.
- CLI providers run directly via subscription credentials if installed; API providers require their respective env keys.
