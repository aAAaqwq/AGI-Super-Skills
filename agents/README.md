# 👥 Agents — C-Suite Digital Executives

> OPC (One Person Company) 团队模板 — 12 个 C-Suite AI Agent

## 架构总览

```
创始人 / 董事长
    ↓ 战略方向
CEO (main)
    ↓ 运营调度 ───────────────────────┐
    ├── CTO + PE (CTO-Dev) ← 代码/架构 │
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

| Agent | 角色 | 核心文件 | 专属 Skills | 精神导师 |
|-------|------|----------|:-----------:|----------|
| [CEO](main/) | 首席执行官 | AGENTS.md | — | — |
| [CTO](coo/) | 首席技术官 | AGENTS/SOUL/MEMORY/USER + [TOOLS](coo/TOOLS.md) | 6 | Kelsey Hightower |
| **[PE](pe/)** | **CTO-Dev** | **AGENTS/SOUL/MEMORY/USER** + **[TOOLS](pe/TOOLS.md)** | **25** | **Linus, antirez, DHH** |
| [CQO](cqo/) | 首席量化官 | AGENTS/SOUL/MEMORY/USER + [TOOLS](cqo/TOOLS.md) | 4 | Jim Simons |
| **[CCO](cco/)** | **首席内容官** | **[AGENTS](cco/AGENTS.md)** + **[TOOLS](cco/TOOLS.md)** | **14** | **MrBeast, 影视飓风** |
| **[CDO](cdo/)** | **首席数据官** | **[AGENTS](cdo/AGENTS.md)** + **[TOOLS](cdo/TOOLS.md)** | **2** | **DJ Patil** |
| [CFO](cfo/) | 首席财务官 | AGENTS/SOUL/MEMORY/USER | 0 | Warren Buffett |
| [CRO](cro/) | 首席研究官 | AGENTS/SOUL/MEMORY/USER + [TOOLS](cro/TOOLS.md) | 3 | Andrej Karpathy |
| [CMO](cmo/) | 首席营销官 | AGENTS/SOUL/MEMORY/USER + [TOOLS](cmo/TOOLS.md) | 2 | Seth Godin |
| [CPO](cpo/) | 首席产品官 | AGENTS/SOUL/MEMORY/USER + [TOOLS](cpo/TOOLS.md) | 3 | Marty Cagan |
| [CLO](clo/) | 首席法务官 | AGENTS/SOUL/MEMORY/USER | 0 | Lawrence Lessig |
| [CSO](cso/) | 首席销售官 | AGENTS/SOUL/MEMORY/USER + [TOOLS](cso/TOOLS.md) | 3 | Aaron Ross |
| [COO](coo/) | 首席运营官 | AGENTS/SOUL/MEMORY/USER + [TOOLS](coo/TOOLS.md) | 6 | Andy Grove |

## Agent 目录结构

```
agents/
├── README.md              ← 本文件（架构总览）
├── cco/                   ← 首席内容官
│   ├── AGENTS.md          ← 角色定义、职责、协作路由
│   └── TOOLS.md           ← 14 个技能索引 → skills/
├── cdo/                   ← 首席数据官
│   ├── AGENTS.md
│   └── TOOLS.md           ← 2 个技能索引 → skills/
├── pe/                    ← CTO-Dev（代码开发）
│   ├── AGENTS.md
│   ├── SOUL.md            ← 人格内核（Linus/antirez/DHH 方法论）
│   ├── MEMORY.md          ← 长期记忆（方法论、项目索引）
│   ├── USER.md            ← 创始人画像
│   └── TOOLS.md           ← 25 个技能索引 → skills/
├── cfo/                   ← 首席财务官
│   ├── AGENTS.md / SOUL.md / MEMORY.md / USER.md
│   └── (无专属 skill)
└── ... (其他 agent 同理)
```

## Skills 索引机制

每个 Agent 的 `TOOLS.md` 通过相对链接 `../skills/<skill-name>/` 指向仓库根目录的 [`skills/`](../skills/) 统一技能库。

**不重复存储** — 所有 skills 只存在于 `skills/` 目录，agent 通过 TOOLS.md 索引引用。

```
agents/cco/TOOLS.md ──→ ../skills/douyin-publish/SKILL.md
agents/cdo/TOOLS.md ──→ ../skills/api-gateway/SKILL.md
agents/pe/TOOLS.md  ──→ ../skills/docker-pro/SKILL.md
```

## 重点关注 Agent

### 🎬 CCO — 首席内容官

跨平台内容生产核心，覆盖视频、图文、音频全品类：

| 能力域 | Skills | 说明 |
|--------|--------|------|
| 视频制作 | jimeng-digital-human, jimeng-storyboard, ai-marketing-videos | AI 视频 + 数字人 |
| 视频工具 | video-merge-send, openai-whisper | 后期处理 |
| 平台发布 | douyin-publish, xiaohongshu-growth, x-articles | 抖音/小红书/X |
| 内容辅助 | content-cover-gen, nano-banana-pro | 封面/图像 |
| 分发 | content-distributor, wechat-toolkit | 一稿多发 |

### 📊 CDO — 首席数据官

数据基础设施，为全团队提供数据能力：

| 能力域 | Skills | 说明 |
|--------|--------|------|
| API 集成 | api-gateway | 100+ 第三方服务统一对接 |
| 文档提取 | mineru-extract | PDF/图片智能提取 |

### 💻 PE — CTO-Dev

工程执行核心，25 个技能覆盖开发全链路：

| 能力域 | Skills 数 | 说明 |
|--------|:---------:|------|
| 架构设计 | 7 | API、认证、React、DB、Redis、CSS、SQL |
| 部署运维 | 4 | Docker、K8s、CI/CD、浏览器 |
| 测试 | 4 | E2E、TDD、反模式、测试生成 |
| 安全 | 1 | 安全审计 |
| Git 协作 | 6 | Review、Worktrees、分支、子代理 |
| 编码代理 | 3 | Claude Code、Codex CC |

## 相关文档

- [团队宪章](../CHARTER.md) — 七大秩序原则、十二条铁律
- [协作网络](../COLLABORATION.md) — Agent 间协作规范
- [启动指南](../STARTUP.md) — 快速上手
- [技能库](../skills/) — 620+ AI skills

---

*基于 [OpenClaw](https://github.com/openclaw/openclaw) 构建 · OPC 团队模板*
