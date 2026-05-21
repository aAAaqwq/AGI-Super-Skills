# Skill: ruflo — AI Agent Orchestration Platform

**Executable:** `ruflo` (installed at `~/.npm-global/bin/ruflo`)
**Version:** v3.7.0-alpha.34
**Source:** ruv.io / [github.com/ruvnet/claude-flow](https://github.com/ruvnet/claude-flow)
**Emoji:** 🔮

---

## What It Does

ruflo is an enterprise AI agent orchestration platform — deploy 60+ specialized agents in coordinated swarms with self-learning, fault-tolerant consensus, vector memory, and MCP integration.

**Core capabilities:**
- **Agent orchestration** — spawn, coordinate, and manage multi-agent swarms
- **Vector memory** — semantic search over agent memory with HNSW indexing (150x–12,500x faster)
- **MCP server** — Model Context Protocol server management
- **Self-learning hooks** — intelligent workflow automation
- **Guidance Control Plane** — compile, retrieve, enforce, and optimize guidance rules
- **Autopilot** — persistent swarm completion (keeps agents working until ALL tasks done)
- **hive-mind** — Queen-led consensus-based multi-agent coordination
- **Flash Attention** — 2.49x–7.47x speedup for embedding operations

---

## When to Use

- You need to orchestrate multiple specialized agents working in coordination
- You want persistent autonomous task completion (autopilot mode)
- You need semantic search over agent memory/knowledge
- You want to route tasks intelligently to specialized agents (Q-Learning-based routing)
- You need MCP server integration for external tools
- You want consensus-based multi-agent decision making (hive-mind)

---

## Key Commands

| Command | Description |
|---------|-------------|
| `ruflo init` | Initialize RuFlo in current directory |
| `ruflo start` | Start the orchestration system |
| `ruflo status` | Show system status |
| `ruflo agent spawn -t <type>` | Spawn a typed agent |
| `ruflo swarm init --v3-mode` | Initialize V3 swarm |
| `ruflo memory search -q "<query>"` | Semantic memory search |
| `ruflo mcp start` | Start MCP server |
| `ruflo hive-mind` | Queen-led multi-agent consensus |
| `ruflo guidance` | Guidance Control Plane management |
| `ruflo autopilot` | Persistent swarm until all tasks complete |
| `ruflo providers` | Manage AI providers/models |
| `ruflo analyze` | Code analysis, diff classification, change risk |
| `ruflo route` | Intelligent task-to-agent routing (Q-Learning) |
| `ruflo hooks` | Self-learning hooks system |
| `ruflo config` | Configuration management |
| `ruflo doctor` | System diagnostics and health checks |
| `ruflo neural` | Neural pattern training, MoE, Flash Attention |

---

## Architecture (V3)

- **15-agent hierarchical mesh** coordination
- **AgentDB** with HNSW indexing
- **Unified SwarmCoordinator** engine
- **Event-sourced** state management
- **DDD** architecture

---

## Examples

### Spawn a coder agent
```bash
ruflo agent spawn -t coder
```

### Initialize a V3 swarm
```bash
ruflo swarm init --v3-mode
```

### Semantic memory search
```bash
ruflo memory search -q "auth patterns"
```

### Start MCP server
```bash
ruflo mcp start
```

### System diagnostics
```bash
ruflo doctor
```

### Intelligent task routing
```bash
ruflo route --task "analyze this codebase"
```

### Autopilot: persistent swarm
```bash
ruflo autopilot --goal "complete all open PR reviews"
```

---

## Integration Notes

**Path:** `~/.npm-global/bin/ruflo`
**Config:** `~/.ruflo/` or project-local `.ruflo/`

ruflo complements OpenClaw for scenarios requiring:
1. **Multi-agent coordination** — spawn specialized ruflo agents for complex tasks
2. **Enhanced memory** — leverage ruflo's vector memory for semantic search
3. **Swarm workflows** — use autopilot + hive-mind for autonomous task completion
4. **Code analysis** — route complex analysis tasks via `ruflo analyze`

---

## Skill Metadata

| Field | Value |
|-------|-------|
| **Type** | External tool / Agent orchestration |
| **Installed** | Yes (npm-global) |
| **Runtime** | Node.js ESM |
| **Author** | ruv.io |
| **Last Verified** | 2026-05-18 |
