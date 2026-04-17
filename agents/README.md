# 👥 Agents — C-Suite Digital Executives

> OPC (One Person Company) 团队模板 — 12 个 C-Suite AI Agent + CEO

## 团队架构

| Agent | 角色 | 核心文件 |
|-------|------|----------|
| CEO | 首席执行官 | 战略协调、任务调度 |
| CTO | 首席技术官 | 系统架构、运维监控 |
| CQO | 首席量化官 | 量化交易、市场分析 |
| CCO | 首席内容官 | 内容创作、深度写作 |
| CDO | 首席数据官 | 数据采集、分析 |
| CFO | 首席财务官 | 财务核算、盈亏分析 |
| CRO | 首席研究官 | 研究分析、情报收集 |
| CMO | 首席营销官 | 市场营销、推广策略 |
| CPO | 首席产品官 | 项目管理、需求分析 |
| CLO | 首席法务官 | 法务合规、合同审核 |
| CSO | 首席销售官 | 商业拓展、客户分析 |
| COO | 首席运营官 | 运营协调、效率优化 |
| PE | CTO-Dev | 代码开发、系统优化 |

## Agent 目录结构

```
agents/
├── cfo/
│   ├── AGENTS.md    ← 工作手册
│   ├── SOUL.md      ← 人格与风格
│   ├── MEMORY.md    ← 长期记忆（方法论）
│   ├── USER.md      ← 创始人画像（通用化）
│   └── skills/      ← Agent 专属技能
├── pe/              ← CTO-Dev（代码开发）
│   ├── AGENTS.md
│   ├── SOUL.md
│   ├── MEMORY.md
│   └── skills/
└── main/            ← CEO
    ├── AGENTS.md
    └── skills/
```

## 使用说明

每个 Agent 目录包含：
- **AGENTS.md** — 角色定义、工作规范、协作网络
- **SOUL.md** — 人格内核、导师方法论、行为准则
- **MEMORY.md** — 长期记忆（方法论、项目索引、决策记录）
- **USER.md** — 创始人画像（去敏版）
- **skills/** — 该 Agent 专属的 OpenClaw skills

## 模板说明

此为通用化 OPC 团队模板，所有个人标识已移除：
- 路径统一为 `/path/to/workspace`、`/path/to/openclaw`
- 人名替换为角色标识 `[创始人]`、`[CQO]` 等
- 私人日志（memory/）不包含在此目录中

## 相关文档

- [团队宪章](../CHARTER.md) — 七大秩序原则、十二条铁律
- [协作网络](../COLLABORATION.md) — Agent 间协作规范
- [启动指南](../STARTUP.md) — 快速上手

---

*基于 [OpenClaw](https://github.com/openclaw/openclaw) 构建*
