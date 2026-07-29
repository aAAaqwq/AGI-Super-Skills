# AGI Super Team for Codex

This directory indexes the curated, Codex-native distribution in `plugins/agi-super-team-codex`. It is intentionally smaller than the repository's full cross-harness skill library so Codex can load high-value workflows without importing every legacy skill.

## Install from `main`

One command handles the marketplace, plugin, global CEO, and Teams:

```bash
npx -y github:aAAaqwq/AGI-Super-Team
npx -y github:aAAaqwq/AGI-Super-Team --install
```

The first command is a non-mutating preview. The second applies the exact plan. The npm-ready short form is `npx -y agi-super-team --install` after the package is published.

Manual equivalent:

```bash
codex plugin marketplace add aAAaqwq/AGI-Super-Team --ref main
codex plugin add agi-super-team-codex@agi-super-team
```

Start a new Codex task after installation. The six workflow Skills below are then available directly. Ask Codex to run `$agi-super-team-sync` to inject the global Musk CEO and install one or all outcome Teams; it previews first, preserves unrelated content, and backs up overwritten files.

## Inject the global CEO and Teams

```bash
SYNC="<installed-plugin>/skills/agi-super-team-sync/scripts/install_codex_team.py"
python3 "$SYNC" --list-teams
python3 "$SYNC" --global-ceo --all-teams
python3 "$SYNC" --global-ceo --all-teams --install
```

Use `--team solo-founder` instead of `--all-teams` for a selective install. The managed CEO block goes into `~/.codex/AGENTS.md`; Team leaves go into `~/.codex/agents/`. Existing content outside the managed block and unrelated Agent files remain untouched. Start a new task after installation.

Install one executive subagent pyramid with `--with-subagents <manager-id>`; supported managers are `cto`, `cpo`, `cco`, `cfo`, `cdo`, `cqo`, `cmo`, `cro`, `cso`, `coo`, and `clo`. Repeat the flag or use `--all-subagents` for all 92 leaves. CTO reuses `ast-pe` as its delivery lead and never creates `ast-cto-pe`.

## Packaged Skills

| Skill | Purpose |
|---|---|
| `c-suite-team` | Parent-as-CEO orchestration across eight outcome Teams, bounded C-suite leaves, Governor review, and honest fallback modes |
| `native-agent-swarms` | Bounded native Codex agent orchestration with ownership, dependencies, messaging, and synthesis gates |
| `project-memory` | Explicit-save project decisions and handoffs without hooks, daemons, or automatic conversation capture |
| `iterative-retrieval` | Evidence-oriented, progressively refined repository and context retrieval |
| `context-engineering` | Context selection, compression, and handoff practices for long or multi-stage tasks |
| `agi-super-team-sync` | Inject the global Musk CEO, install selected Teams, or safely sync all bundled Agent TOMLs |

## Outcome Teams

| Team ID | 用途 | 核心角色 |
|---|---|---|
| `solo-founder` | 单人创业、MVP、商业验证与融资准备 | CEO、CPO、PE、CCO、CMO、Governor |
| `content-creator` | 研究驱动的内容选题、生产与复盘 | CEO、CRO、CCO、CDO、CMO、Governor |
| `quant-trader` | 量化研究、数据质量、风险与资本约束 | CEO、CQO、CDO、CFO、CRO、Governor |
| `product-delivery` | 产品发现、架构、实现、数据与验收 | CEO、CPO、CTO、PE、CDO、Governor |
| `research-decision` | 高不确定性研究与管理决策 | CEO、CRO、CDO、CFO、CLO、Governor |
| `go-to-market` | 定位、增长、内容、销售、财务与法务 | CEO、CPO、CRO、CMO、CCO、CSO、CFO、CLO、CDO、Governor |
| `operations-response` | 事故指挥、恢复、合规与复盘 | CEO、COO、CTO、PE、CDO、CLO、Governor |
| `full-team` | 公司级跨职能综合任务 | 全部 14 个 C-suite 角色 |

## Packaged Agents

The plugin bundles 136 roles: 31 general engineering/review specialists, 13 generated C-suite roles, and 92 opt-in child specialists routed by eleven manager executives. The current parent is the CEO, so no second CEO Agent is installed. Governor remains independent and PE remains CTO's canonical delivery leaf. Most roles are read-only; bounded implementation roles use workspace-write.

| Domain | Agents |
|---|---|
| Executive outcome teams | `ast-cto`, `ast-pe`, `ast-cpo`, `ast-cqo`, `ast-cmo`, `ast-cfo`, `ast-cdo`, `ast-cco`, `ast-clo`, `ast-cro`, `ast-cso`, `ast-coo`, `ast-governor` |
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
max_depth = 2
job_max_runtime_seconds = 1800
interrupt_message = true
```

The parent and one executive manager occupy two threads, leaving room for at most two direct children. Run manager groups in waves; multiple managers with children must not be flattened into one oversized wave.

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
| Executive child agents | `jnMetaCode/agency-agents-zh@2ecfabf8e944ccdfed63ad8c44d5241290af6977` | MIT | 92 byte-locked Chinese source files plus separate local routing and safety envelopes |
| Project memory | Codex-native local adaptation, 2026-07-21 | Repository license | Explicit save/recall/archive only; no transcript scan or background capture |

The larger Ruflo/Claude Flow, raw Claude agent-team, automatic conversation-memory, and full ECC surfaces are not bundled. They remain library candidates until their hooks, MCP servers, runtimes, privacy boundaries, and Codex semantics are reviewed independently.

## Layout

```text
.agents/plugins/marketplace.json       Codex marketplace entry
.codex/INDEX.md                        This index
plugins/agi-super-team-codex/
├── .codex-plugin/plugin.json          Plugin manifest
├── payload/global/AGENTS.md           Managed global Musk CEO guidance
├── payload/agents/*.toml              136 installable agents
└── skills/                            Six curated Codex skills
```
