<p align="center">
  <img src="assets/logo.png" alt="AGI Super Team" width="120">
</p>

<h1 align="center">AGI Super Team</h1>

<p align="center">
  <strong>727 AI Skills · 12 C-Suite Agents · 29 Thinking Frameworks</strong><br/>
  Build your AI-native company in minutes.
</p>

<p align="center">
  <a href="https://github.com/openclaw/openclaw"><img src="https://img.shields.io/badge/Powered%20by-OpenClaw-blue?logo=github" alt="OpenClaw"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Skills-727-blueviolet" alt="Skills">
  <img src="https://img.shields.io/badge/Agents-12-orange" alt="Agents">
  <img src="https://img.shields.io/badge/Frameworks-29-cyan" alt="Frameworks">
</p>

<p align="center">
  <a href="./README_CN.md">中文</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="./skills/README.md">All Skills</a> ·
  <a href="./agents/README.md">Agents</a> ·
  <a href="./cookbook/">Cookbooks</a>
</p>

---

## 💡 What Is This?

A **plug-and-play AI team template** — deploy a complete virtual C-Suite using [OpenClaw](https://github.com/openclaw/openclaw). Each agent has a **spirit mentor** (Elon Musk, Jensen Huang, Warren Buffett...) that shapes their personality and decision-making.

**727 skills. 12 agents. 29 thinking frameworks. 30 workflows.** Zero boilerplate — copy, customize, ship.

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

29 distilled thinking skills based on real-world mentors — mental models, decision frameworks, classic quotes with sources:

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

| Category | Highlights |
|----------|-----------|
| 🔌 SaaS Integrations | Notion, Airtable, HubSpot, Stripe, ActiveCampaign, 60+ more |
| 📝 Content & Writing | SEO, viral copy, anti-AI-slop, social media |
| 🔧 Development | Backend, frontend, Docker, Git, TDD, API design, code review |
| 💰 Trading & Finance | Crypto, Polymarket, DeFi, portfolio management, backtesting |
| ⚙️ OpenClaw Tools | Config, auth, cron, MCP, token guard, agent orchestration |
| 🤖 AI Agent Patterns | Multi-agent orchestration, parallel execution, sub-agents |
| 📊 Data & Analytics | Web scraping, DuckDB, CSV pipelines, arXiv |
| 📈 Marketing & SEO | SEO audits, GEO optimization, A/B testing, competitor analysis |
| 🎨 Design & Media | Image generation, UI/UX, brand identity |
| 🏢 Business & Strategy | SaaS launch, competitor teardown, financial modeling |
| 📋 Project Management | PRD, roadmaps, Scrum, team coordination |
| 💬 Communication | Email, Feishu, WeChat, Telegram, LinkedIn, cross-instance messaging |
| 📱 Chinese Platforms | Xiaohongshu, Douyin, WeChat MP, Juejin, Zhihu |
| ⚙️ DevOps & Infra | AWS, Docker, Linux, observability, deployment |
| 🧬 Bioinformatics | Genome analysis, metagenomics, pharmacogenomics |
| 🎬 Video & Digital Human | Video editing, digital human, storyboard, subtitle |
| 🤖 Web3 & Autonomys | Decentralized storage, auto-deploy, auto-memory |

👉 **[Full skill catalog →](./skills/README.md)**

## 🔄 Workflows

30 production-ready workflows across all C-Suite roles:

| Scope | Examples |
|-------|---------|
| **Shared** | Daily standup, weekly review, crisis escalation, cross-agent handoff |
| **Per-Agent** | Content pipeline (CCO), market morning brief (CQO), P&L tracking (CFO), code review (PE), incident response (COO) |

Each agent directory (e.g. `agents/cco/WORKFLOW.md`) contains role-specific and shared workflows.

## Quick Start

### Prerequisites

Install [OpenClaw](https://github.com/openclaw/openclaw) (AI agent runtime):
```bash
npm install -g openclaw
openclaw init
```

### Deploy your AI team

```bash
# 1. Clone the repo
git clone https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team

# 2. Deploy an agent (e.g., CEO with Elon Musk's thinking)
mkdir -p ~/.openclaw/workspace-main/skills/
cp -r skills/thinking-elon-musk/ ~/.openclaw/workspace-main/skills/
cp agents/main/SOUL.md agents/main/AGENTS.md ~/.openclaw/workspace-main/

# 3. Add more skills
cp -r skills/api-design/ ~/.openclaw/workspace-main/skills/

# 4. Deploy more agents (e.g., PE for coding)
mkdir -p ~/.openclaw/workspace-pe/skills/
cp agents/pe/SOUL.md agents/pe/AGENTS.md ~/.openclaw/workspace-pe/
cp -r skills/thinking-linus-torvalds/ ~/.openclaw/workspace-pe/skills/

# 5. Restart OpenClaw — done!
openclaw gateway restart
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
├── skills/           # 727 skills (flat structure, each with SKILL.md)
│   └── README.md     # Full catalog

├── cookbook/         # 5 in-depth learning guides
├── CHARTER.md        # Team constitution (12 principles)
├── STARTUP.md        # Quick-start guide
├── COLLABORATION.md  # Inter-agent collaboration network
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
