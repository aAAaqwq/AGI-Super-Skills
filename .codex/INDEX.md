# AGI Super Team for Codex

This directory indexes the curated, Codex-native distribution in `plugins/agi-super-team-codex`. It is intentionally smaller than the repository's full cross-harness skill library so Codex can load high-value workflows without importing every legacy skill.

## Install from `main`

```bash
codex plugin marketplace add aAAaqwq/AGI-Super-Team --ref main
codex plugin add agi-super-team-codex@agi-super-team
```

Start a new Codex task after installation. The four workflow skills below are then available directly. To install or update the bundled personal agent roles, ask Codex to run `$agi-super-team-sync`; it previews changes first and backs up overwritten agent files.

## Packaged Skills

| Skill | Purpose |
|---|---|
| `native-agent-swarms` | Bounded native Codex agent orchestration with ownership, dependencies, messaging, and synthesis gates |
| `project-memory` | Explicit-save project decisions and handoffs without hooks, daemons, or automatic conversation capture |
| `iterative-retrieval` | Evidence-oriented, progressively refined repository and context retrieval |
| `context-engineering` | Context selection, compression, and handoff practices for long or multi-stage tasks |
| `agi-super-team-sync` | Preview and safely copy bundled agent TOMLs into the user's Codex agent directory |

## Packaged Agents

The plugin bundles 31 specialist roles. Most are read-only reviewers or planners; only `debugger`, `tdd-guide`, and `test-automator` request workspace-write access for implementation work.

| Domain | Agents |
|---|---|
| Orchestration and planning | `team-coordinator`, `planner`, `architect`, `context-manager` |
| Architecture and engineering | `architecture-reviewer`, `backend-architect`, `frontend-reviewer`, `ai-engineer`, `legacy-modernizer` |
| Language and data | `typescript-reviewer`, `python-reviewer`, `database-reviewer`, `vector-database-engineer`, `mle-reviewer` |
| Quality and debugging | `code-reviewer`, `quality-engineer`, `debugger`, `hypothesis-debugger`, `tdd-guide`, `test-automator` |
| Security and operations | `security-reviewer`, `threat-modeler`, `devops-troubleshooter`, `incident-responder`, `kubernetes-architect`, `terraform-specialist`, `observability-reviewer`, `performance-reviewer` |
| Product surfaces and knowledge | `accessibility-reviewer`, `docs-reviewer`, `search-conversations` |

`search-conversations` is an optional adapter: it reports semantic conversation search as unavailable unless the user separately configures a compatible memory backend. No conversation database or automatic capture system is bundled.

## Recommended Native-Agent Limits

The plugin does not modify `~/.codex/config.toml`. Review these conservative defaults before adding them manually:

```toml
[agents]
max_threads = 4
max_depth = 1
job_max_runtime_seconds = 1800
interrupt_message = true
```

The parent agent occupies one thread, so a four-thread limit normally permits two or three useful workers without unbounded fan-out.

## Security and Update Policy

- No credentials, private memories, conversation databases, user configuration, hooks, daemons, or background processes are packaged.
- Agent synchronization defaults to dry-run, never deletes unrelated files, and backs up every differing agent file before replacement.
- The selected project-memory workflow only saves information when explicitly requested.
- The plugin copy is canonical after installation. If same-named personal skills already exist, review and archive those copies only with explicit user approval to avoid maintaining two versions.
- Pull updates from the repository's `main` branch, then refresh Codex with:

  ```bash
  codex plugin marketplace upgrade agi-super-team
  codex plugin add agi-super-team-codex@agi-super-team
  ```

- Every plugin release increments the manifest semantic version (or uses the Codex cachebuster helper) so clients do not reuse stale content.

## Sources and Provenance

| Asset | Upstream revision | License | Migration decision |
|---|---|---|---|
| Professional agents and swarm patterns | `wshobson/agents@767d969a73ce6608d10ac713e52be9ac7f061ab9` | MIT | Selected roles rewritten as Codex TOML plus native orchestration guidance |
| Iterative retrieval | `affaan-m/everything-claude-code@0f84c0e2796703fbda87d577b2636351418c7442` | MIT | Adapted without installing the full ECC plugin |
| Context engineering | `addyosmani/agent-skills@6ce029897d2b794940325fc7148774a6ec51111c` | MIT | Packaged as a focused Codex skill |
| Project memory | Codex-native local adaptation, 2026-07-21 | Repository license | Explicit save/recall/archive only; no transcript scan or background capture |

The larger Ruflo/Claude Flow, raw Claude agent-team, automatic conversation-memory, and full ECC surfaces are not bundled. They remain library candidates until their hooks, MCP servers, runtimes, privacy boundaries, and Codex semantics are reviewed independently.

## Layout

```text
.agents/plugins/marketplace.json       Codex marketplace entry
.codex/INDEX.md                        This index
plugins/agi-super-team-codex/
├── .codex-plugin/plugin.json          Plugin manifest
├── payload/agents/*.toml              31 installable specialist agents
└── skills/                            Five curated Codex skills
```
