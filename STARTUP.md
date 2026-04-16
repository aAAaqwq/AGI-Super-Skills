# 🚀 AGI Super Team 启动指南

> Deploy your own AI-native C-Suite in minutes.

## 📋 Prerequisites

- [Node.js](https://nodejs.org/) v20+
- [OpenClaw](https://github.com/openclaw/openclaw) installed globally
- API keys for your preferred AI providers (Anthropic, OpenAI, Google, ZAI, etc.)
- A Telegram account (for bot-based agents)

## 🚀 Quick Deploy

```bash
# 1. Clone the repository
git clone https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team

# 2. Install OpenClaw (if not already)
npm install -g openclaw

# 3. Deploy agent configs
cp -r agents/<agent-id> ~/.openclaw/agents/

# 4. Deploy skills
cp -r skills/<skill-name> ~/.openclaw/skills/
# Or symlink for easy updates:
# ln -s $(pwd)/skills/<skill-name> ~/.openclaw/skills/

# 5. Configure API keys
openclaw config

# 6. Start the gateway
openclaw gateway start
```

## 👥 C-Suite Team Members

| ID | Role | Spirit Mentor | Focus |
|----|------|---------------|-------|
| `main` | 👑 CEO — 首席执行官 | Elon Musk | Strategy, coordination, quality |
| `code` | ⚡ CTO — 首席技术官 | Jensen Huang | Code, architecture, debugging |
| `product` | 🎨 CPO — 首席产品官 | Steve Jobs | Product design, UX, brand |
| `quant` | 📈 CQO — 首席质量官 | Jim Simons | Quant trading, analysis |
| `market` | 📣 CMO — 首席营销官 | David Ogilvy | Marketing, SEO, growth |
| `finance` | 💰 CFO — 首席财务官 | Warren Buffett | Finance, P&L, cost optimization |
| `data` | 📊 CDO — 首席数据官 | Nate Silver | Data scraping, ETL, analytics |
| `content` | ✍️ CCO — 首席内容官 | Jony Ive + MrBeast | Content, viral creation |
| `law` | ⚖️ CLO — 首席法务官 | Alan Dershowitz | Legal, compliance, contracts |
| `research` | 🔬 CRO — 首席研究官 | Richard Feynman | Deep research, intelligence |
| `sales` | 🤝 CSO — 首席战略官 | Michael Dell | Sales, BD, customer analysis |
| `ops` | ⚙️ COO — 首席运营官 | Andy Grove | Ops, monitoring, efficiency |
| `pm` | 📋 CQO — 首席项目官 | — | Project management, coordination |

Each agent has:
- **`agent.json`** — Model, skills, bot config, system prompt
- **`SOUL.md`** — Personality, values, communication style, spirit mentor
- **`AGENTS.md`** — Role definition, responsibilities, collaboration network
- **`TOOLS.md`** — Tool notes, recommended skills, API index

## ✅ First Run Checklist

- [ ] OpenClaw installed (`openclaw --version`)
- [ ] API Key configured (`openclaw config`)
- [ ] Agent configs reviewed and customized
- [ ] Telegram Bot token set (if using Telegram)
- [ ] Skills deployed to `~/.openclaw/skills/`
- [ ] Gateway running (`openclaw gateway start`)
- [ ] Test message sent and received

## 📁 Repository Structure

```
AGI-Super-Team/
├── agents/              # Agent configurations (C-Suite)
│   ├── main/            # 👑 CEO
│   ├── code/            # ⚡ CTO
│   ├── product/         # 🎨 CPO
│   ├── ...              # Other C-Suite members
│   └── README.md        # Agent documentation
├── skills/              # 510 curated AI skills
│   ├── categories/      # Skills organized by category
│   ├── docs/            # Skill documentation
│   └── README.md        # Skill index
├── cookbook/             # Knowledge cookbooks (complete chapter books)
│   ├── celebrity-mindset/    # 27 chapters on top entrepreneurs
│   ├── knowledge-book/       # 10-chapter knowledge system
│   ├── quant-learning/       # 20-round quantitative trading curriculum
│   ├── self-media-operations-handbook/  # 11-chapter operations guide
│   ├── crypto-learning/      # Complete crypto trading guide
│   └── prompt-engineering-learning/     # 6-round prompt engineering course
├── CHARTER.md           # Team charter
├── COLLABORATION.md     # Collaboration guidelines
├── SECURITY.md          # Security policy
├── STARTUP.md           # This file
└── README.md            # Main documentation
```

## 🎨 Customization

### Swap Models
Edit `agent.json` → `model` field. Supports any OpenClaw-compatible provider:
- Anthropic: `anthropic/claude-opus-4`, `anthropic/claude-sonnet-4`
- OpenAI: `openai/gpt-4o`, `openai/o3`
- Google: `google/gemini-2.5-pro`
- ZAI: `zai/glm-5`
- And more...

### Add Skills
```bash
# From this repo
cp -r skills/<skill-name> ~/.openclaw/skills/

# From ClawHub
openclaw skills install <skill-name>
```

### Create New Agent
```bash
# Copy a template
cp -r agents/code ~/.openclaw/agents/my-custom-agent

# Edit config
vim ~/.openclaw/agents/my-custom-agent/agent.json
vim ~/.openclaw/agents/my-custom-agent/SOUL.md

# Restart
openclaw gateway restart
```

## 🌐 Multi-Machine Deployment

Connect agents across machines with Tailscale:
```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
tailscale up

# OpenClaw will auto-discover peers
openclaw gateway start
```

## 📚 Learn More

- [OpenClaw Documentation](https://github.com/openclaw/openclaw)
- [Agent Configuration Guide](./agents/README.md)
- [Skill Categories](./skills/categories/README.md)
- [Knowledge Cookbooks](./cookbook/) — Multi-chapter learning resources

## 🤝 Support

- **Issues**: [GitHub Issues](https://github.com/aAAaqwq/AGI-Super-Team/issues)
- **PRs**: Contributions welcome! See [Contributing](./README.md#-contributing)

---

*Built with ⚙️ by the AGI Super Team — Day 1, every day.*
