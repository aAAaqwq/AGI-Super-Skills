# 四框架的真实发现与委派机制

最后核对：2026-07-30。版本或配置变化时应重新查阅官方文档，不把本表当作永久不变的 API。

| 框架 | Agent / Skill 如何发现 | 原生委派与 Team | AGI Super Team 的安全执行方式 |
|---|---|---|---|
| Claude Code | `CLAUDE.md` 提供持久上下文；项目/用户级 `.claude/agents/` 发现自定义 Agent；`.claude/skills/` 发现 Skills | Subagent 使用独立上下文，普通 Subagent 不能再创建 Subagent。Agent Teams 是实验功能，由 Lead、Teammates、共享任务列表和邮箱构成 | 普通模式由主会话/Lead 平铺调用 C-suite 与叶子；只有实验功能已启用且用户同意时才使用 Agent Teams。不要预造静态 Team 状态文件 |
| Codex | 分层 `AGENTS.md` 注入指令；用户 Skills 的官方目录是 `~/.agents/skills/`；自定义 Agent 位于 `~/.codex/agents/*.toml` | 父 Agent 管理子 Agent 树、消息和等待；真实可用深度与并发受当前配置和版本约束 | 先读连接清单和本机 Agent 限制。深度不足时由主 Agent 平铺 Manager/Leaf 或顺序交接；不要声称发生两层嵌套 |
| OpenClaw | `agents.list` 定义 Agent；workspace、managed、bundled 目录提供 Skills；Agent 的 `skills` 字段是明确 allowlist | `sessions_spawn` 创建隔离会话；`allowAgents` 控制跨 Agent ID 调用；sessions 工具负责等待与查证 | 仅调用 `connection.json` 中精确 ID，并复核 `agents.list`、skill allowlist 与 `subagents.allowAgents`。用独立 Governor 会话读取原始证据 |
| Hermes | `~/.hermes/skills/` 提供渐进式 Skills；Profile 由其 SOUL、Skills 与配置组成 | `delegate_task` 创建同步、隔离的短任务；leaf 不可继续委派，orchestrator 需显式提高深度。Kanban 是跨 Profile/人工的持久工作队列 | 命名 C-suite 和长期协作用 Profile + Kanban；一次性窄任务用 `delegate_task`。Profile blueprint 只代表安装准备，不代表 Profile 已创建或运行 |

## Claude Code

- 自定义 Subagent 文档：<https://code.claude.com/docs/en/sub-agents>
- Agent Teams 文档：<https://code.claude.com/docs/en/agent-teams>
- 扩展能力概览：<https://code.claude.com/docs/en/features-overview>

普通 Subagent 不能继续创建 Subagent，因此 canonical 的 CEO→Manager→Leaf 是组织语义，不保证天然等同于运行时嵌套。默认由主会话或 Team Lead 按顺序/平铺执行。Agent Teams 仍需实验开关，且是否组队受用户批准；不要把 `~/.claude/teams/` 的运行时文件当成仓库内静态配置。

## Codex

- AGENTS.md：<https://learn.chatgpt.com/docs/agent-configuration/agents-md>
- Skills：<https://developers.openai.com/codex/skills/>
- Subagents：<https://developers.openai.com/codex/multi-agent/>

Skill 可由 `$skill-name` 显式触发，或由 `description` 语义匹配。安装器同时写入官方 `~/.agents/skills/` 与兼容目录 `~/.codex/skills/` 时，以前者作为运行时入口；兼容副本不应被解释为重复能力。

启动前检查 `~/.codex/config.toml` 或当前会话暴露的限制。如果本机只允许一层子 Agent，主 Agent可直接调 Manager 和 Leaf，但必须将模式记为 `lead-flat`，不能伪造 Manager→Leaf 运行轨迹。

## OpenClaw

- Agent 配置：<https://docs.openclaw.ai/gateway/config-agents>
- Skills：<https://docs.openclaw.ai/tools/skills>
- sessions 工具：<https://docs.openclaw.ai/gateway/config-tools>

Skills 是否可见不仅取决于路径，也取决于依赖门、Agent allowlist 和当前 workspace。`agents.list[].skills: []` 表示没有 Skill，不是继承全部。Adapter 的结构校验或 `openclaw config validate` 不能替代真实 canary。

## Hermes

- Skills：<https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/skills.md>
- Delegation：<https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/delegation.md>
- Kanban：<https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/kanban.md>

`delegate_task` 是函数调用和一次性子任务，不是持久命名 Team。需要 C-suite 身份、跨轮次状态或人工接管时，使用 Profile 与 Kanban；没有 CLI、Profile 或任务回执时，状态保持 `structural-only` 或 `pending`。

## 证据等级

1. `planned`：仅生成预览。
2. `filesystem-connected`：文件已写入且清单可解析。
3. `config-validated`：框架配置通过静态验证。
4. `canary-observed`：真实启动、触发、委派和回传已观察。
5. `revision-matched`：canary/receipt 与干净的仓库 revision、连接摘要一致。

不得跨级推断。例如，发现 106 个 Agent 文件不能证明语义触发成功；一次手工 canary 也不能自动升级另一个 commit 的 receipt。
