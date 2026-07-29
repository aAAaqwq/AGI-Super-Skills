# 👥 Agents — C-Suite Digital Executives

> OPC (One Person Company) 团队模板 — 14 个 C-Suite AI Agent，即插即用

## 架构总览

```
创始人 / 董事长
    ↓ 战略方向
CEO (ceo)
    ↓ 运营调度 ───────────────────────┐
    ├── CTO → PE + 22 工程子专家       │
    ├── CQO → 4 量化子专家             │
    ├── CCO → 19 内容增长子专家        │ 跨部门
    ├── CDO → 5 数据子专家             │ 通过 CEO
    ├── CFO → 8 财务子专家             │ 协调
    ├── CRO → 6 研究子专家             │
    ├── CMO → 7 营销子专家             │
    ├── CPO → 3 设计子专家             │
    ├── CLO → 6 法务合规子专家         │
    ├── CSO → 8 销售子专家             │
    ├── COO → 4 运营子专家 ───────────┘
    └── Governor ← 治理验证（三证验真）
```

子 Agent 目录采用可审计金字塔：

```text
agents/
├── cto/subagents/<role>/AGENTS.md   # 22 个工程专家；PE 复用 agents/pe
├── cpo/subagents/<role>/AGENTS.md   # UI、UX 研究、UX 架构
├── cco/subagents/<role>/AGENTS.md   # 19 个内容增长专家
├── cfo/subagents/<role>/AGENTS.md   # 8 个财务专家
├── cdo/subagents/<role>/AGENTS.md   # 5 个数据专家
├── cqo/subagents/<role>/AGENTS.md   # 4 个量化专家
├── cmo/subagents/<role>/AGENTS.md   # 7 个营销专家
├── cro/subagents/<role>/AGENTS.md   # 6 个研究专家
├── cso/subagents/<role>/AGENTS.md   # 8 个销售专家
├── coo/subagents/<role>/AGENTS.md   # 4 个运营专家
└── clo/subagents/<role>/AGENTS.md   # 6 个法务合规专家
```

这些 `AGENTS.md` 是固定上游 commit 的逐字副本；组织关系、触发和安全规则分别由 `config/agent-hierarchy.json` 与 `config/*-specialists.json` 管理，来源哈希由 `config/agent-sources.lock.json` 锁定。不要直接修改 vendored 子 Agent 原文。

## Agent 速查表

| Agent | 角色 | 精神导师 | 核心文件 |
|-------|------|----------|----------|
| [CEO](ceo/) | 👑 首席执行官 | Elon Musk | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · WORKFLOW |
| [CTO](cto/) | ⚡ 首席技术官 | Jensen Huang | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · TOOLS |
| [PE](pe/) | 💻 首席工程师 | Linus, antirez, DHH | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · WORKFLOW · TOOLS |
| [CQO](cqo/) | 📈 首席量化官 | Jim Simons | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · WORKFLOW · TOOLS |
| [CCO](cco/) | ✍️ 首席内容官 | MrBeast, 影视飓风 | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · WORKFLOW · TOOLS |
| [CDO](cdo/) | 📊 首席数据官 | Nate Silver, DJ Patil | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · WORKFLOW · TOOLS |
| [CFO](cfo/) | 💰 首席财务官 | Warren Buffett | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · WORKFLOW |
| [CMO](cmo/) | 📣 首席营销官 | David Ogilvy, Seth Godin | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · WORKFLOW · TOOLS |
| [CPO](cpo/) | 🎨 首席产品官 | Steve Jobs, Marty Cagan | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · TOOLS |
| [CLO](clo/) | ⚖️ 首席法务官 | Alan Dershowitz | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP |
| [CRO](cro/) | 🔬 首席研究官 | Richard Feynman, Karpathy | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · WORKFLOW · TOOLS |
| [CSO](cso/) | 🤝 首席销售官 | Michael Dell, Aaron Ross | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · TOOLS |
| [COO](coo/) | ⚙️ 首席运营官 | Andy Grove, Jeff Bezos | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · WORKFLOW · TOOLS |
| [Governor](governor/) | ⚖️ 治理官（三省合一） | 诸葛亮, 王阳明 | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · TOOLS |

> **PE = 首席工程师（Principal Engineer）**，负责全栈工程和 DevOps 执行
> **Governor = 治理官**，融合三省职能（定法/执法/验真），负责交付验证与质量管控

## Agent 目录结构

每个 agent 目录包含完整的 persona 文件：

```
agents/cco/                    ← 示例：首席内容官
├── AGENTS.md                  ← 角色定义、职责、协作路由
├── SOUL.md                    ← 人格内核（精神导师方法论）
├── IDENTITY.md                ← 详细身份档案
├── BOOTSTRAP.md               ← 启动引导流程
├── MEMORY.md                  ← 长期记忆（方法论、项目索引）
├── USER.md                    ← 用户画像
├── WORKFLOW.md                ← 标准工作流 + 团队共享流程
└── TOOLS.md                   ← 专属技能索引 → skills/
```

### 文件说明

| 文件 | 用途 | 必需 |
|------|------|:----:|
| `AGENTS.md` | 角色定义、工作规范、汇报标准 | ✅ |
| `SOUL.md` | 人格内核、导师方法论、行为准则 | ✅ |
| `IDENTITY.md` | 详细身份档案、存在意义、核心特质 | ✅ |
| `BOOTSTRAP.md` | 启动引导、必读文件、工作模式 | ✅ |
| `MEMORY.md` | 长期记忆、项目索引、经验教训 | ✅ |
| `USER.md` | 用户画像、偏好、上下文 | ✅ |
| `WORKFLOW.md` | 角色工作流 + 团队共享流程 | ✅ |
| `TOOLS.md` | 专属技能链接索引 | ⚡ |

## Skills 索引机制

每个 Agent 的 `TOOLS.md` 通过相对链接 `../skills/<skill-name>/` 指向仓库根目录的 [`skills/`](../skills/) 统一技能库。

**不重复存储** — 所有 skills 只存在于 `skills/` 目录，agent 通过 TOOLS.md 索引引用。

```
agents/cco/TOOLS.md ──→ ../skills/douyin-smart-publish/SKILL.md
agents/cdo/TOOLS.md ──→ ../skills/api-gateway/SKILL.md
agents/pe/TOOLS.md  ──→ ../skills/docker-containerization/SKILL.md
```

## 快速部署

先安装到一次性目录并检查预览；默认只预览，不写入文件：

```bash
AGI_TEAM_DEST="$(mktemp -d "${TMPDIR:-/tmp}/agi-super-team.XXXXXX")"

./install.sh --source "$PWD" --destination "$AGI_TEAM_DEST" --agent cco
```

确认角色、Skills 和目标路径无误后，再显式应用：

```bash
./install.sh --source "$PWD" --destination "$AGI_TEAM_DEST" --apply --agent cco
```

安装团队组合、选择 Skills 层级及接入 Codex 等 Harness 的完整步骤见[启动指南](../setup.md)。安装器只生成可检查的文件，不会自动启动模型或注册 Agent。

## 相关文档

- [团队宪章](../CHARTER.md) — 七大秩序原则、十二条铁律
- [协作网络](../COLLABORATION.md) — Agent 间协作规范
- [启动指南](../STARTUP.md) — 快速上手
- [技能库](../skills/) — 完整 AI Skills 目录

---

*兼容 Claude Code / Codex / Cursor / Hermes · OPC 团队模板*
