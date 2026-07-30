---
name: orchestrate-agi-super-team
description: 按 Team→C-suite→Skills/直属 Subagents→Governor→CEO→人工批准契约编排 AGI Super Team。适用于用户要求跨职能团队、专家委派、独立复核，或需在 Claude Code、Codex、OpenClaw、Hermes 中选择真实执行方式；单领域一步任务不要启用。
---

# AGI Super Team 编排

用同一份组织契约选择最小充分团队，再把它翻译成当前框架真正支持的运行方式。安装成功只说明资产可发现；没有 canary 或 receipt 证据时，不得声称委派已验证。

## 先读取什么

1. 需要判断框架能力、安装路径或降级方式时，读取 [references/framework-mechanisms.md](references/framework-mechanisms.md)。
2. 需要生成任务包、工作流和验收记录时，读取 [references/execution-contract.md](references/execution-contract.md)。
3. 若仓库中存在 `config/team-manifest.json`、`config/agent-hierarchy.json` 和 `config/*-specialists.json`，以它们为组织关系事实来源。
4. 若已安装 Adapter，读取当前框架的 `agi-super-team/connection.json` 与 `receipt.json`；只调用其中真实存在、被允许的运行时 ID。

## 编排工作流

### 1. 定义成果

写清成果、成功标准、约束、非目标、截止条件和必须由人类批准的现实动作。把事实、假设、推断和未知分开；重大外部事实使用当前一手来源。

### 2. 选择 Team 与最小角色集

优先匹配已有 Team Kit；否则按职责选择 1 个 CEO 协调者、2–3 个互补 C-suite/PE，以及需要时的 Governor。不要为了展示阵容而启用 `full-team`。

### 3. 生成路由图

按以下两条并行支路连接角色，禁止把 Skill 当 Agent，也禁止把目录嵌套当委派权限：

```text
Team → C-suite → 专属 Skills ─────────────┐
              └→ 允许调用的 Subagents → 专家产物
                                           ↓
工作产物 → Governor 独立复核 → CEO 综合 → 人工批准
```

- `C-suite → Skill`：选择完成工作所需的方法，不把全部 Skills 注入每个叶子。
- `C-suite → Subagent`：只从当前 Manager 的 allowlist 中按触发条件选择专家。
- 叶子只完成窄任务，回传产物、证据、检查、限制和下一步，不继续委派。

### 4. 选择当前框架能兑现的模式

先识别框架，再按参考文档选择以下一种模式，并在计划中明确写出：

- `native-tree`：当前框架和深度限制允许 CEO→Manager→Leaf。
- `lead-flat`：主会话/Lead 平铺调用 Manager 与 Leaf，语义层级保留在任务包中。
- `sequential-handoff`：没有可靠并行或嵌套时，主 Agent 顺序执行相同契约。
- `structural-only`：只有文件与映射，没有运行时证据；只输出安装/接线结论，不伪称已调度。

Claude Code 的普通 Subagent 不能继续创建 Subagent；Codex 必须服从当前深度配置；OpenClaw 必须使用连接清单中的精确 Agent ID；Hermes 的 Profile/Kanban 与 `delegate_task` 是两种不同机制。详见框架参考。

### 5. 委派自包含任务包

每个任务包至少包含：负责人、目标、输入、允许读取的来源、预期产物、边界、验收、依赖、回传格式。只有互不依赖且能缩短关键路径的任务才并行。

### 6. 独立复核与人工门

重大结论、发布、资金、法律、安全或完成声明交给 Governor；提供原始声明、产物和验证证据，不要求其迎合 CEO。CEO 综合决定与异议，但不得改写有证据支持的审查结论。

登录、发布、部署、凭证、付款、交易、法律承诺、对外联系、生产写入和其他不可逆动作必须由人类最终批准。

### 7. 输出编排记录

最终必须包含：

- 选用的 Team、角色和选择理由；
- 当前框架、运行模式与降级原因；
- 实际调用的 Agent/Skill，以及未调用项；
- 工作产物、验证证据、Governor 异议；
- 人工批准点、剩余风险、负责人和下一步；
- receipt/canary 状态：`verified`、`pending` 或 `failed`，不得自行升级。

## 停止条件

- 单个角色即可完成：停止组队，直接执行。
- 运行时 ID 不在连接清单：停止调用，先修复安装或映射。
- 所需深度超过框架限制：改用 `lead-flat` 或 `sequential-handoff`。
- 缺少原始证据或人类批准：停在建议/草案，不执行现实写入。
- Governor 发现未解决的高风险问题：回到负责角色修正，不能用 CEO 表决覆盖。
