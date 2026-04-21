# 👥 Agents — C-Suite Digital Executives

> OPC (One Person Company) 团队模板 — 12 个 C-Suite AI Agent，即插即用

## 架构总览

```
创始人 / 董事长
    ↓ 战略方向
CEO (main)
    ↓ 运营调度 ───────────────────────┐
    ├── CTO + PE (首席工程师) ← 代码   │
    ├── CQO ← 量化交易                 │
    ├── CCO ← 内容/视频                │ 跨部门
    ├── CDO ← 数据/API                 │ 通过 CEO
    ├── CFO ← 财务                     │ 协调
    ├── CRO ← 研究                     │
    ├── CMO ← 营销/SEO                 │
    ├── CPO ← 产品                     │
    ├── CLO ← 法务                     │
    ├── CSO ← 销售                     │
    └── COO ← 运维/安全 ──────────────┘
```

## Agent 速查表

| Agent | 角色 | 精神导师 | 核心文件 |
|-------|------|----------|----------|
| [CEO](main/) | 👑 首席执行官 | Elon Musk | AGENTS · SOUL · MEMORY · IDENTITY · BOOTSTRAP · WORKFLOW |
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

> **PE = 首席工程师（Principal Engineer）**，负责全栈工程和 DevOps 执行

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

```bash
# 部署单个 agent
cp -r agents/cco/* ~/.openclaw/workspace-cco/
cp -r skills/douyin-smart-publish/ ~/.openclaw/workspace-cco/skills/

# 部署全部 agent
for agent in main cto cpo cqo cmo cfo cdo cco clo cro cso coo pe; do
  mkdir -p ~/.openclaw/workspace-${agent}/
  cp -r agents/${agent}/* ~/.openclaw/workspace-${agent}/
done
```

## 相关文档

- [团队宪章](../CHARTER.md) — 七大秩序原则、十二条铁律
- [协作网络](../COLLABORATION.md) — Agent 间协作规范
- [启动指南](../STARTUP.md) — 快速上手
- [技能库](../skills/) — 700+ AI skills

---

*基于 [OpenClaw](https://github.com/openclaw/openclaw) 构建 · OPC 团队模板*
