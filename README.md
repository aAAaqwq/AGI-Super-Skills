<p align="center">
  <img src="logo.png" alt="AGI Super Team" width="120">
</p>

<h1 align="center">AGI Super Team</h1>

<p align="center">
  <strong>637 AI Skills + 12 C-Suite Agents</strong> — Build your AI-native company in minutes.
</p>

<p align="center">
  <a href="https://github.com/openclaw/openclaw"><img src="https://img.shields.io/badge/Powered%20by-OpenClaw-blue?logo=github" alt="OpenClaw"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Skills-637-blueviolet" alt="Skills">
  <img src="https://img.shields.io/badge/Agents-12-orange" alt="Agents">
  <img src="https://img.shields.io/badge/Thinking%20Frameworks-32-cyan" alt="Frameworks">
</p>

<p align="center">
  <a href="./README_CN.md">中文</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="./skills/README.md">All Skills</a> ·
  <a href="./agents/README.md">Agents</a> ·
  <a href="./cookbook/">Cookbooks</a> ·
  <a href="./workflows/">Workflows</a>
</p>

---

## 💡 What Is This?

A **plug-and-play AI team template** — deploy a complete virtual C-Suite using [OpenClaw](https://github.com/openclaw/openclaw). Each agent has a **spirit mentor** (Elon Musk, Jensen Huang, Warren Buffett...) that shapes their personality and decision-making.

**637 skills. 12 agents. 32 thinking frameworks. 31 workflows.** Zero boilerplate — copy, customize, ship.

## 🏛️ Architecture

```
You (Founder / Chairman)
  └── 👑 CEO — Strategy, coordination, quality gate
        ├── ⚡ CTO — Code, architecture, debugging
        ├── 🎨 CPO — Product design, UX, brand DNA
        ├── 📈 CQO — Quant trading, market analysis
        ├── 📣 CMO — Marketing, SEO, growth
        ├── 💰 CFO — Finance, P&L, cost optimization
        ├── 📊 CDO — Data scraping, ETL, analytics
        ├── ✍️ CCO — Content creation, viral growth
        ├── ⚖️ CLO — Legal, compliance, contracts
        ├── 🔬 CRO — Deep research, intelligence
        ├── 🤝 CSO — Sales, BD, customer analysis
        ├── ⚙️ COO — Ops, monitoring, efficiency
        └── 💻 PE  — Full-stack engineering, DevOps
```

## 👥 Agents

| Agent | Role | Spirit Mentor | Thinking |
|-------|------|---------------|----------|
| [`ceo`](./agents/ceo/) | 👑 CEO | Elon Musk | First Principles, Critical Thinking |
| [`cto`](./agents/cto/) | ⚡ CTO | Jensen Huang | Systems Thinking, Technical Depth |
| [`cpo`](./agents/cpo/) | 🎨 CPO | Steve Jobs | Design Thinking, User Empathy |
| [`cqo`](./agents/cqo/) | 📈 CQO | Jim Simons | Mathematical Rigor, Probabilistic Thinking |
| [`cmo`](./agents/cmo/) | 📣 CMO | David Ogilvy | Storytelling, Audience Psychology |
| [`cfo`](./agents/cfo/) | 💰 CFO | Warren Buffett | Value Investing, Margin of Safety |
| [`cdo`](./agents/cdo/) | 📊 CDO | Nate Silver | Bayesian Thinking, Data-Driven |
| [`cco`](./agents/cco/) | ✍️ CCO | MrBeast | Viral Mechanics, Platform Algorithm |
| [`clo`](./agents/clo/) | ⚖️ CLO | Alan Dershowitz | Legal Reasoning, Risk Assessment |
| [`cro`](./agents/cro/) | 🔬 CRO | Richard Feynman | Scientific Method, First Principles |
| [`cso`](./agents/cso/) | 🤝 CSO | Michael Dell | Sales Engineering, Relationship Building |
| [`coo`](./agents/coo/) | ⚙️ COO | Andy Grove | High Output Management, Measurement |

> Each agent folder contains `SOUL.md` (personality), `AGENTS.md` (operations), `TOOLS.md` (skill links). Fully customizable.

## 🧠 Thinking Frameworks

32 distilled thinking skills based on real-world mentors — mental models, decision frameworks, classic quotes with sources:

```bash
# Inject a mentor's thinking into any agent
cp -r skills/thinking-elon-musk/ ~/.openclaw/workspace-main/skills/

# Or inject all frameworks to all workspaces
for agent in main cto cpo cqo cmo cfo cdo cco clo cro cso coo pe; do
  mkdir -p ~/.openclaw/workspace-${agent}/skills/
  cp -r skills/thinking-* ~/.openclaw/workspace-${agent}/skills/
done
```

## 🛠️ Skill Categories

| Category | Count | Highlights |
|----------|:-----:|-----------|
| 🔌 SaaS Integrations | 62 | Notion, Airtable, HubSpot, Stripe, 55+ more |
| 📝 Content & Writing | 38 | SEO, viral copy, anti-AI-slop, social media |
| 🔧 Development | 35 | Backend, frontend, Docker, Git, TDD, API design |
| 💰 Trading & Finance | 32 | Crypto, Polymarket, DeFi, portfolio management |
| ⚙️ OpenClaw Tools | 28 | Config, auth, cron, MCP, token guard |
| 🤖 AI Agent Patterns | 25 | Multi-agent orchestration, parallel execution |
| 📊 Data & Analytics | 21 | Web scraping, DuckDB, CSV pipelines, arXiv |
| 📈 Marketing & SEO | 19 | SEO audits, GEO optimization, A/B testing |
| 🎨 Design & Media | 15 | Image generation, UI/UX, brand identity |
| 🏢 Business & Strategy | 15 | SaaS launch, competitor teardown, financial modeling |
| 📋 Project Management | 18 | PRD, roadmaps, Scrum, team coordination |
| 💬 Communication | 13 | Email, Feishu, WeChat, cross-instance messaging |
| 📱 Chinese Platforms | 13 | Xiaohongshu, Douyin, WeChat MP, Juejin |
| ⚙️ DevOps & Infra | 10 | AWS, Docker, Linux, observability |
| 🎬 Video & Digital Human | 5 | Digital human, video merge, storyboard |
| 🧩 Other | 18 | RSS, calendars, presentations, design thinking |

👉 **[Full skill catalog →](./skills/README.md)**

## 🔄 Workflows

31 production-ready workflows across all C-Suite roles:

| Scope | Examples |
|-------|---------|
| **Shared** | Daily standup, weekly review, crisis escalation, cross-agent handoff |
| **Per-Agent** | Content pipeline (CCO), market morning brief (CQO), P&L tracking (CFO), code review (PE), incident response (COO) |

👉 **[All workflows →](./workflows/README.md)**

## 🚀 Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team

# 2. Deploy an agent (e.g., CEO)
mkdir -p ~/.openclaw/workspace-main/skills/
cp -r skills/thinking-elon-musk/ ~/.openclaw/workspace-main/skills/

# 3. Add skills to any agent
cp -r skills/code-review/ ~/.openclaw/workspace-main/skills/

# 4. Restart OpenClaw — done!
```

## 📚 Cookbooks

In-depth learning guides in [`cookbook/`](./cookbook/):

| Book | Description |
|------|-------------|
| [Self-Media Operations](./cookbook/self-media-operations-handbook/) | Complete handbook: XHS, Douyin, WeChat, content strategy |
| [Quantitative Trading](./cookbook/quant-learning/) | Crypto trading, algorithmic strategies, risk management |
| [Prompt Engineering](./cookbook/prompt-engineering-learning/) | Advanced prompt techniques and patterns |
| [Knowledge Base](./cookbook/knowledge-book/) | Cross-domain knowledge distillation |
| [Crypto Deep Dive](./cookbook/crypto-learning/) | Blockchain fundamentals and DeFi |

## 📁 Repository Structure

```
AGI-Super-Team/
├── agents/           # 12 C-Suite agent personas
│   ├── ceo/          # SOUL.md · AGENTS.md · TOOLS.md
│   ├── cto/          # ...
│   └── README.md     # Architecture diagram & skill matrix
├── skills/           # 637 skills (20 categories)
│   ├── README.md     # Full catalog with ratings
│   └── categories/   # Per-category indexes
├── workflows/        # 31 standard operating procedures
├── cookbook/         # 5 in-depth learning guides
├── CHARTER.md        # Team constitution (12 principles)
├── STARTUP.md        # Quick-start guide
└── COLLABORATION.md  # Inter-agent collaboration network
```

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

1. Fork the repo
2. Create your skill: `skills/your-skill/SKILL.md`
3. Submit a PR

## 📄 License

[MIT](./LICENSE) — use freely, attribution appreciated.

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
  Built with ❤️ using <a href="https://github.com/openclaw/openclaw">OpenClaw</a>
</p>
