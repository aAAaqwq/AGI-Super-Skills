<p align="center">
  <img src="assets/logo.png" alt="AGI Super Team" width="120">
</p>

<h1 align="center">AGI Super Team</h1>

<p align="center">
  <strong>部署一支由传奇大脑驱动的 AI 高管团队。</strong><br/>
  让 Jim Simons 跑量化 · MrBeast 做爆款 · 巴菲特管钱。
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Works%20with-Claude%20Code%20%7C%20Codex%20%7C%20Cursor-blueviolet" alt="Harness compatible">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Skills-1,651-blueviolet" alt="Skills">
  <img src="https://img.shields.io/badge/Agents-14-orange" alt="Agents">
  <img src="https://img.shields.io/badge/Frameworks-31-cyan" alt="Frameworks">
</p>

<p align="center">
  <a href="./README.md">English</a> ·
  <a href="#quick-start">快速开始</a> ·
  <a href="./skills/README.md">全部技能</a> ·
  <a href="./agents/README.md">Agent</a> ·
  <a href="./cookbook/">教程</a> ·
  <a href="./workflows/">工作流</a>
</p>

---

## 💡 这是什么？

一个**即插即用的 AI 团队模板** — 兼容 Claude Code / Codex / Cursor 等 AI 编程助手，部署完整的虚拟 C-Suite。每个 Agent 都有**精神导师**（Elon Musk、Jensen Huang、Warren Buffett...）塑造其性格和决策方式。

**1,651 技能 · 14 个 Agent · 31 个思维框架 · 30 个工作流。** 零配置 — 复制、定制、发布。

## ⚡ 安装

> **原生支持 Claude Code、Cursor、Codex、Gemini。**

```bash
# Claude Code（推荐）
/plugin install aAAaqwq/AGI-Super-Team

# OpenAI Codex —— 精选原生 Swarm、记忆能力与 31 个专业 Agent
codex plugin marketplace add aAAaqwq/AGI-Super-Team --ref main
codex plugin add agi-super-team-codex@agi-super-team

# 或直接克隆
git clone --depth 1 https://github.com/aAAaqwq/AGI-Super-Team.git ~/.agi-super-team
```

完整 Agent 清单、安全同步流程、更新命令与来源说明见 [Codex 包索引](./.codex/INDEX.md)。

一键 kit 部署（solo-founder / quant-trader / content-creator 等）见下方[10 分钟你能做什么](#10-分钟你能做什么)。

## 🚀 10 分钟你能做什么

三个杀手级用例 —— 每个都由仓库内置的实战 skill 支撑，绑定对应的传奇大脑。

### 📈 量化交易 —— Jim Simons 为你操盘
部署 **quant-trader kit**，CQO（Jim Simons）立即开始运行实战策略：
- **`5minbtc`** —— BTC 5 分钟方向预测（v5.7.3 引擎，实盘验证）
- **`a-share-analysis`** —— A 股量化分析，一键每日脚本
- **`a-fund-monitor`** —— 基金净值实时估算 + Telegram 推送

```bash
curl -sSL https://raw.githubusercontent.com/aAAaqwq/AGI-Super-Team/main/install.sh | bash -s -- quant-trader
```

### 📣 爆款内容 —— MrBeast 的玩法
部署 **content-creator kit**，CCO（MrBeast）接管内容：
- **`xhs-content-creator`** / **`xhs-skill`** —— 为小红书算法打造的内容
- **`wechat-article-writer`** / **`wechat-ai-radar`** —— 公众号文章 + 每日情报
- **`content-cover-gen`** —— 内容驱动的封面图生成

```bash
curl -sSL https://raw.githubusercontent.com/aAAaqwq/AGI-Super-Team/main/install.sh | bash -s -- content-creator
```

### 🏛️ 完整高管团队 —— 你的 AI 原生公司
14 位高管、1,651 技能、31 套思维框架 —— 一行命令：

```bash
curl -sSL https://raw.githubusercontent.com/aAAaqwq/AGI-Super-Team/main/install.sh | bash -s -- full-team
```

> 每个 kit 会把对应的 skill 装进 `~/.openclaw/workspace-{agent}/skills/`，并绑定到匹配的高管 Agent。无需手动配置。

## 🏛️ 架构

```
你（创始人 / 董事长）
  └── 👑 CEO — 战略、协调、质量把关
        ├── ⚡ CTO — 代码、架构、调试
        ├── 🎨 CPO — 产品设计、用户体验、品牌
        ├── 📈 CQO — 量化交易、市场分析
        ├── 📣 CMO — 营销、SEO、增长
        ├── 💰 CFO — 财务、利润、成本优化
        ├── 📊 CDO — 数据采集、ETL、分析
        ├── ✍️ CCO — 内容创作、病毒式增长
        ├── ⚖️ CLO — 法律、合规、合同
        ├── 🔬 CRO — 深度研究、情报
        ├── 🤝 CSO — 销售、商务拓展
        ├── ⚙️ COO — 运营、监控、效率
        └── 💻 PE  — 全栈工程、DevOps
```

## 🚀 快速开始

> 推荐使用上方[安装](#安装)章节的原生 plugin 入口；下面的手动方式适合需要细粒度控制的用户。

```bash
# 1. 克隆仓库
git clone https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team

# 2. 部署 Agent（例如 CEO）
mkdir -p ~/.openclaw/workspace-ceo/skills/
cp -r skills/thinking-elon-musk/ ~/.openclaw/workspace-ceo/skills/

# 3. 给任何 Agent 添加技能
cp -r skills/api-design/ ~/.openclaw/workspace-ceo/skills/

# 4. 重启你的 Agent harness — 完成！
```

## 🛠️ 技能分类

| 分类 | 亮点 |
|------|------|
| 🔧 开发 | 前端、后端、Docker、Git、TDD、API 设计 |
| 💰 交易与金融 | 加密货币、Polymarket、量化策略、回测 |
| 📝 内容与写作 | SEO、病毒文案、反AI检测、社交媒体 |
| 📈 营销与SEO | SEO 审计、GEO 优化、竞品分析 |
| 📱 中国平台 | 小红书、抖音、微信公众号、知乎、掘金 |
| 🔌 SaaS 集成 | 60+ 平台：HubSpot、Stripe、Airtable 等 |
| 🎬 视频与媒体 | AI 视频、数字人、FFmpeg、字幕 |
| 🤖 AI Agent 模式 | 多 Agent 编排、并行执行、子 Agent |
| 🧬 生物信息学 | 基因组分析、药物基因组学 |

👉 **[完整技能目录 →](./skills/README.md)**

## 📚 教程

| 教程 | 描述 |
|------|------|
| [自媒体运营手册](./cookbook/self-media-operations-handbook/) | 小红书、抖音、微信完整运营策略 |
| [量化交易](./cookbook/quant-learning/) | 加密货币、算法策略、风险管理 |
| [Prompt 工程](./cookbook/prompt-engineering-learning/) | 高级提示词技术与模式 |

## 📁 仓库结构

```
AGI-Super-Team/
├── agents/           # 14 个 C-Suite Agent
├── skills/           # 1,651 个技能（扁平结构）
├── workflows/        # 30 个标准工作流
├── cookbook/         # 5 个深度教程
├── CHARTER.md        # 团队宪章
└── STARTUP.md        # 快速开始指南
```

## 📄 许可证

[MIT](./LICENSE) — 自由使用，请注明出处。

---

## ⭐ Star History

<a href="https://star-history.com/#aAAaqwq/AGI-Super-Team&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=aAAaqwq/AGI-Super-Team&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=aAAaqwq/AGI-Super-Team&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=aAAaqwq/AGI-Super-Team&type=Date" />
 </picture>
</a>

---

<p align="center">
  兼容 Claude Code / Codex / Cursor / Hermes 等 AI 编程助手
</p>
