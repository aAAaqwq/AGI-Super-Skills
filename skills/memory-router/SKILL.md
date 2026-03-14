---
name: memory-router
description: Team-wide memory routing skill — routes agent queries to the optimal knowledge source (QMD hybrid search, daily memory, MEMORY.md) and enforces citation. Use when any agent needs to retrieve prior work, system config, skill docs, project status, or decisions. Triggers on "查知识库", "memory router", "qmd query", "find in docs", "what was decided", "how does X work", "项目状态", "之前的决策".
---

# Memory Router — Team Unified Knowledge Retrieval Skill

## Purpose

All team agents (小a/ops/code/quant/data/finance/research/market/pm/content/law) MUST route knowledge retrieval through this standardized pipeline before answering questions about:
- 系统配置、架构、部署
- 历史决策、TODO、进度
- Skill 用法与触发条件
- 项目状态与交付件
- 人物、日期、数字

## QMD Feature Map (all features agents should use)

| Feature | Command | When to Use |
|---------|---------|-------------|
| **Hybrid search** | `qmd query "<question>"` | DEFAULT: combines BM25 + vector + rerank. Best for most queries |
| **Structured query** | `qmd query $'lex: keyword\nvec: semantic'` | When you need precise keyword AND semantic results |
| **BM25 keyword** | `qmd search "<exact term>"` | Exact term/filename/config key lookup |
| **Vector similarity** | `qmd vsearch "<concept>"` | Conceptual/fuzzy similarity (e.g., "how to deploy") |
| **Get document** | `qmd get path/to/file.md:42 -l 30` | Read specific lines after search identifies a file |
| **Multi-get** | `qmd multi-get "reports/*.md"` | Batch fetch multiple files (e.g., all reports) |
| **Collection filter** | `qmd query -c skills "<question>"` | Restrict search to one collection for precision |
| **Full output** | `qmd query --full "<question>"` | Get complete document content instead of snippets |
| **JSON output** | `qmd query --json "<question>"` | Machine-readable output for scripts |
| **List files** | `qmd ls skills` | Browse what's indexed in a collection |
| **Status** | `qmd status` | Health check: pending embeds, collection sizes |
| **Update index** | `qmd update` | Re-index after file changes |
| **Embed vectors** | `qmd embed` | Generate embeddings for new/changed files |
| **Context notes** | `qmd context list` | View collection descriptions/usage hints |
| **MCP server** | `qmd mcp` | Expose as MCP tool for IDE/agent integration |

## Collections (current)

| Collection | Content | Use For |
|------------|---------|---------|
| `clawd-memory` | `~/clawd/**/*.md` (1603 files) | Memory, docs, reports, runbooks |
| `daily-memory` | `~/clawd/memory/*.md` (44 files) | Daily work logs |
| `team` | `~/.openclaw/agents/**/*.json` (860 files) | Agent configs, models, auth |
| `openclaw-config` | `~/.openclaw/**/*.json` (1031 files) | OpenClaw system config |
| `projects` | `~/clawd/projects/**/*.md` (100 files) | Project PRDs, deliverables |
| `skills` | `~/clawd/skills/**/SKILL.md` (468 files) | All skill documentation |
| `reports` | `~/clawd/reports/*.md` (2 files) | Research & review reports |

## Routing Algorithm

```
Input: user question Q

Step 1 — CLASSIFY
  A = "prior decisions / todos / people / dates / what happened"
  B = "system config / how-to / skill usage / architecture"
  C = "project status / deliverables / PRD"
  D = "external facts / live data" (falls through to web)

Step 2 — RETRIEVE (execute ALL applicable, not just one)

  if A:
    → qmd query -c daily-memory "<Q>" -n 5
    → qmd query -c clawd-memory "<Q>" -n 5
    → Also check ~/clawd/MEMORY.md directly for TODOs/decisions

  if B:
    → qmd query -c openclaw-config "<Q>" -n 5
    → qmd query -c skills "<Q>" -n 5
    → qmd query -c clawd-memory "<Q>" -n 3  (for runbooks/docs)

  if C:
    → qmd query -c projects "<Q>" -n 5
    → qmd query -c reports "<Q>" -n 3

  if D:
    → qmd query "<Q>" -n 5  (all collections, no filter)
    → If low recall → web_fetch / browser

Step 3 — CITE
  Every answer MUST include 1-3 source citations:
  - File path: `~/clawd/docs/memory-router.md:15`
  - QMD URI: `qmd://skills/geo-agent/SKILL.md`
  - Or: "Source: qmd query -c projects 'content factory status'"
```

## Agent Integration (mandatory AGENTS.md section)

Each agent's AGENTS.md must contain:

```markdown
## 知识库 / Memory Router（强制）

- 你在回答任何「配置/流程/历史/怎么做」类问题前，**必须先检索本地知识库**：
  1) 优先 QMD：`qmd query "<问题>"`（必要时加 `--collection openclaw-config|projects|skills|reports|clawd-memory`）
  2) 涉及待办/决策/人/日期 → 再查工作区记忆文件（`~/clawd/memory/YYYY-MM-DD.md` 与 `~/clawd/MEMORY.md`）
- 输出时至少引用 1-3 个来源（文件路径或 `qmd://...` URI）。
```

## Health Monitoring

### Daily Cron (recommended)
```bash
# qmd-health: run daily at 08:00
qmd status | grep -E "Total|Vectors|Pending|Updated"
qmd update
```

### Weekly Embed Refresh
```bash
# qmd-embed: run weekly Sunday 03:00
qmd embed
qmd status
```

### Health Metrics to Track
- **覆盖率**: Vectors / Total (target: >90%)
- **Pending**: should be <100 after weekly embed
- **Collection freshness**: Updated timestamps should be <24h for active collections
- **Query latency**: hybrid query should return <2s

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `qmd embed` hangs | Check if node-llama-cpp is compiling (first run). Wait ~10min. |
| CUDA errors | Normal on CPU-only servers. QMD auto-falls back to CPU. |
| Ollama not found | QMD uses node-llama-cpp, NOT Ollama. Ignore Ollama references. |
| Low recall | Try `--full` flag, or use `qmd search` (BM25) for exact terms |
| Missing files | Run `qmd update` to re-index, then `qmd embed` for new vectors |

## Script: memory_router.sh

For automated context injection into agent prompts:

```bash
#!/bin/bash
# Usage: ./memory_router.sh "question" [collection]
QUERY="$1"
COLLECTION="${2:-}"

if [ -n "$COLLECTION" ]; then
  qmd query -c "$COLLECTION" "$QUERY" -n 5 --line-numbers
else
  qmd query "$QUERY" -n 5 --line-numbers
fi
```

---

Last updated: 2026-03-03
Maintainer: 小a (CEO)
