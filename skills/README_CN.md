<p align="right"><a href="./README.md">English</a></p>

# 🧰 Skills 技能库

按需要交付的成果查找可复用方法。目录中的每个条目都必须是受版本控制的实体目录，并包含 `SKILL.md`；仓库禁止用软链接伪装已收录的 Skill。

优先从小型 Team Pack 开始。库存丰富可以扩大覆盖面，但不表示所有条目的质量、可移植性和支持等级相同。

## 🚀 从这里开始

| 目标 | 维护入口 | 证据边界 |
|---|---|---|
| 规划、开发和沟通 | [Solo Founder](../starter-kits/solo-founder/) | 三个活跃 Agent 工作区；通用安装器已有测试 |
| 研究、创作和测量 | [Content Creator](../starter-kits/content-creator/) | 支持创作流程；发布仍由人类控制 |
| 回测并审查风险 | [Quant Trader](../starter-kits/quant-trader/) | 仅用于研究，不声称支持实盘交易 |
| 使用 Codex 原生工作流 | [Codex 精选包](../.codex/INDEX.md) | 独立维护的精选分发与同步策略 |

## 👥 Skills 与 C-suite 专家

Skill 是可复用方法，Agent 是对结果负责的角色契约。仓库目前包含 14 个顶层角色，以及由 11 位管理型高管精确路由的 92 个可选直属专家。安装专家不会复制整套 Skills；管理者先选出最窄的合适角色，专家再按任务读取必要的方法和工具。

- 组织结构与允许的父子边：[`config/agent-hierarchy.json`](../config/agent-hierarchy.json)
- 正向/排除触发、输入、交付、验收和边界：[`config/*-specialists.json`](../config/)
- 固定上游路径和逐字节哈希：[`config/agent-sources.lock.json`](../config/agent-sources.lock.json)
- 人类可读的 Agent 指南：[`agents/README.md`](../agents/README.md)

```bash
# 预览一个高管军团；审查后追加 --install
npx -y github:aAAaqwq/AGI-Super-Team --tool codex --with-subagents cmo

# 安装全部 92 个直属专家
npx -y github:aAAaqwq/AGI-Super-Team --tool codex --all-subagents --install
```

Codex 包的 136 个角色由 31 个通用工程/审查 Agent、13 个 C-suite Agent 文件和 92 个高管直属专家组成。CEO 继续担任父级协调者，Governor 保持独立，PE 仍是 CTO 的权威生产交付叶子。

## 🧭 按成果浏览 Skills

[自动生成的技能目录](../catalog/)会把每个权威入口归入一个主要类别；[机器可读索引](../catalog/skill-index.json)支持搜索和后续筛选，不需要把 README 维护成数据库。

| 类别 | 类别 | 类别 |
|---|---|---|
| [🤖 AI Agents 与编排](../catalog/#ai-agents-orchestration) | [💻 软件工程](../catalog/#software-engineering) | [☁️ 云、DevOps 与可靠性](../catalog/#cloud-devops-reliability) |
| [📊 数据、分析与研究](../catalog/#data-analytics-research) | [🛡️ 安全、隐私与法律](../catalog/#security-privacy-legal) | [🎨 产品、设计与 UX](../catalog/#product-design-ux) |
| [📈 营销、SEO 与增长](../catalog/#marketing-seo-growth) | [✍️ 内容、媒体与发布](../catalog/#content-media-publishing) | [🤝 销售、CRM 与客户成功](../catalog/#sales-crm-customer-success) |
| [💹 财务、交易与市场](../catalog/#finance-trading-markets) | [🧭 商业运营与战略](../catalog/#business-operations-strategy) | [⚙️ 应用与工作流自动化](../catalog/#apps-workflow-automation) |
| [🇨🇳 中国平台工作流](../catalog/#chinese-platform-workflows) | [🧰 专业领域与通用工具](../catalog/#general-utilities) | |

已知名称或关键词时可在本地搜索：

```bash
rg -n '^description:' skills -g SKILL.md
npm run check:skills
```

## 🏷️ 支持等级与可移植性

- **Curated**：在具名分发中经过审查和版本管理，有独立同步策略。
- **Pack-required**：被活跃 Agent 引用，并受仓库结构检查覆盖。
- **Catalog**：仓库中存在实体 `SKILL.md`；行为、依赖、许可证和客户端支持仍可能需要审查。
- **External**：Manifest 推荐，但没有打包进本仓库。

可移植性是另一条独立维度：

- **Portable required / optional**：由通用安装器复制，并检查已知宿主机路径和运行时专属命令。
- **Harness-specific**：已分配给 Agent，但依赖特定运行时或工具，因此通用安装器会跳过。
- **Catalog-only**：可以发现，但尚未分配给活跃 Agent。

这些标签既不是质量排名，也不是运行保证。使用前应检查权限、依赖、来源和许可证。

## 🔬 结构质量证据

[`catalog/skill-quality.json`](../catalog/skill-quality.json)发布所有权威入口的确定性结构检查，区分硬性结构失败、渐进披露警告，以及仍需人工检查的脚本证据。

```bash
npm run build:skill-quality
npm run check:skill-quality
```

受版本控制的[质量债务基线](../config/skill-quality-baseline.json)允许问题减少，但会在已知问题数量回退时阻止 CI。它不评价语义质量、安全性或真实运行效果。

## 📦 库存契约

权威规则和活跃依赖位于 [`config/team-manifest.json`](../config/team-manifest.json)。分类规则位于 [`config/skill-taxonomy.json`](../config/skill-taxonomy.json)；生成数量不手工维护。主要成果分类通过固定的[人工复核 Gold Set](../docs/skill-taxonomy-gold-set.md)和[机器可读一致性报告](../catalog/skill-taxonomy-evaluation.json)校验，该分数不代表 Skill 质量或安全性。

验证器只统计被 Git 跟踪、不是软链接、存在于工作树且具有顶层 `SKILL.md` 的 Skill：

```bash
npm run build:skills
npm test
npm run validate -- --warnings-as-errors
```

旧版 [Agent 矩阵](../docs/skills-matrix.md)只保留作历史研究视图，不是当前库存或 Agent 分配权威。

## 🧹 已移除链接与来源

可移植性重构中删除的机器本地链接记录在 [`config/external-skill-sources.json`](../config/external-skill-sources.json)。只有在来源、许可证、固定版本、实体内容和验证状态明确后，才应恢复条目。

## 🤝 贡献

新增或恢复 Skill 时，需要清晰指令、可追溯来源、许可证兼容、明确依赖，并确保没有秘密或宿主机专属路径。

不要把占位内容、批量重复内容、不受支持的兼容性声明，或缺乏维护目的的 Skill 放入精选目录。完整规则见 [CONTRIBUTING.md](../CONTRIBUTING.md)。
