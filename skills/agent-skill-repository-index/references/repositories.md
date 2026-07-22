# Daniel's Recommended GitHub Skill Sources

This portable source index is used by AGI Super Team. A maintainer may keep reviewed mirrors under a private `<repository-mirror-root>/<local>` directory; verify each remote and commit before migration. See [star-snapshot.md](star-snapshot.md) for Daniel's supplied July 2026 popularity snapshot and [installing.md](installing.md) for the safe lifecycle workflow. Stars do not determine safety.

## Tier S

| Repository | Local | Class | Best use |
|---|---|---|---|
| [anthropics/skills](https://github.com/anthropics/skills) | `skills` | LIBRARY | Official reference implementations and format conventions. |
| [obra/superpowers](https://github.com/obra/superpowers) | `superpowers` | LIBRARY | Engineering methodology; use its Codex plugin only when explicitly wanted. |
| [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) | `everything-claude-code` | LIBRARY; runtime QUARANTINE | Broad operator patterns; select passive skills only. |
| [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) | `andrej-karpathy-skills` | DAILY | Compact coding-behavior guardrails. |
| [mattpocock/skills](https://github.com/mattpocock/skills) | `mattpocock-skills` | LIBRARY with selected DAILY | TypeScript, teaching, writing, QA, planning, and issue workflows. |
| [leonxlnx/taste-skill](https://github.com/leonxlnx/taste-skill) | `taste-skill` | LIBRARY with selected DAILY | Anti-slop interface design; `design-taste-frontend` is the reviewed global candidate. |
| [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | `claude-code-best-practice` | LIBRARY; examples QUARANTINE | Claude Code concepts, settings, hooks, and MCP examples. |

## Tier A

| Repository | Local | Class | Best use |
|---|---|---|---|
| [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | `awesome-claude-code` | LIBRARY | Claude Code resource discovery. |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | `agent-skills` | LIBRARY with selected DAILY | Production SDLC workflows. |
| [alchaincyf/nuwa-skill](https://github.com/alchaincyf/nuwa-skill) | `nuwa-skill` | LIBRARY | Researching and distilling people’s mental models. |
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | `awesome-claude-skills` | LIBRARY; connectors QUARANTINE | Large discovery catalog; review auth actions separately. |
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | `impeccable` | DAILY candidate | UI anti-pattern audit and design quality. |
| [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) | `planning-with-files` | DAILY | Persistent file-backed planning; keep one canonical installation. |
| [Lum1104/Understand-Anything](https://github.com/Lum1104/Understand-Anything) | `Understand-Anything` | LIBRARY; automation QUARANTINE | Knowledge graphs; services and hooks remain opt-in. |
| [VoltAgent/awesome-openclaw-skills](https://github.com/VoltAgent/awesome-openclaw-skills) | `awesome-openclaw-skills` | LIBRARY | OpenClaw/ClawHub discovery. |
| [LearnPrompt/ai-news-radar](https://github.com/LearnPrompt/ai-news-radar) | `ai-news-radar` | DAILY reader; pipeline LIBRARY | Zero-key AI news reader; publishing pipeline is separate. |
| [composio-community/awesome-codex-skills](https://github.com/composio-community/awesome-codex-skills) | `awesome-codex-skills` | LIBRARY; connectors QUARANTINE | Codex-oriented skill discovery. |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | `claude-skills` | LIBRARY | Broad production catalog; select one domain skill at a time. |
| [wshobson/agents](https://github.com/wshobson/agents) | `agents` | LIBRARY with plugin candidates | Specialist agents and single-purpose plugins. |
| [ruvnet/claude-flow](https://github.com/ruvnet/claude-flow) | `claude-flow` | QUARANTINE runtime; docs LIBRARY | Orchestration, hooks, daemon, federation, and persistent memory. |

## Tier B

| Repository | Local | Class | Best use |
|---|---|---|---|
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | `awesome-agent-skills` | LIBRARY | Cross-agent discovery; trace every item to upstream. |
| [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | `claude-mem` | QUARANTINE | Persistent memory, hooks, worker, database, and MCP. |
| [supermemoryai/supermemory](https://github.com/supermemoryai/supermemory) | `supermemory` | QUARANTINE | Memory/RAG platform with external data and profiles. |
| [garrytan/gstack](https://github.com/garrytan/gstack) | `gstack` | LIBRARY methods; runtime QUARANTINE | Founder workflows; full setup adds browser, daemon, deploy, and updater behavior. |
| [ruvnet/ruflo](https://github.com/ruvnet/ruflo) | `ruflo` | DUPLICATE / QUARANTINE | Same current code lineage as `claude-flow`; choose one canonical source. |
| [0xfurai/claude-code-subagents](https://github.com/0xfurai/claude-code-subagents) | `claude-code-subagents` | LIBRARY | Claude-specific specialist prompt library. |
| [robwhite4/claude-memory](https://github.com/robwhite4/claude-memory) | `claude-memory` | QUARANTINE | Background session rotation, backups, and persistent memory. |

## Specialty

| Repository | Local | Class | Best use |
|---|---|---|---|
| [zarazhangrui/frontend-slides](https://github.com/zarazhangrui/frontend-slides) | `frontend-slides` | LIBRARY / design candidate | HTML presentations; deployment and runtime downloads remain explicit. |
| [nashsu/AutoCLI](https://github.com/nashsu/AutoCLI) | `AutoCLI` | QUARANTINE | Authenticated browser state, extension, adapters, and optional cloud sync. |
| [ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) | `daily_stock_analysis` | QUARANTINE application | Financial-analysis application, scheduled automation, and push channels. |

## General Discovery

| Repository | Local | Class | Best use |
|---|---|---|---|
| [sindresorhus/awesome](https://github.com/sindresorhus/awesome) | `awesome` | LIBRARY | General curated-list index. It has no `SKILL.md` and does not overlap functionally with `taste-skill`. |

## Selection Rules

1. Search installed Codex-native skills before migrating anything.
2. Prefer a narrow upstream skill over an aggregator copy.
3. Read the candidate `SKILL.md` completely and inspect its adjacent resources.
4. Scan for secrets, hooks, persistence, external writes, deployment, tunnels, and auto-update behavior.
5. Record provenance, pinned commit, license, adaptations, trigger examples, and non-trigger examples.
6. Link or copy only the reviewed skill directory; never expose the entire repository by default.
