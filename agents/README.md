# 👥 Agents — AI Team Templates

> [← Back to main README](../README.md)

Ready-to-deploy agent configurations for building your own AI-native company.

## Team Roster

| ID | Role | Files | Description |
|----|------|-------|-------------|
| [`main`](./main/) | 🧠 CEO / Coordinator | agent.json | Central orchestrator — dispatches tasks, reviews output, makes decisions |
| [`code`](./code/) | 💻 Chief Engineer | agent.json, SOUL.md, AGENTS.md | Backend/frontend development, architecture, debugging, deployment |
| [`quant`](./quant/) | 📈 Chief Trading Officer | agent.json, SOUL.md, AGENTS.md | Quantitative trading, market analysis, strategy backtesting |
| [`data`](./data/) | 📊 Chief Data Officer | agent.json, SOUL.md, AGENTS.md | Web scraping, ETL pipelines, data analysis, data cleaning |
| [`ops`](./ops/) | ⚙️ Chief DevOps | agent.json, SOUL.md, AGENTS.md | System monitoring, OpenClaw maintenance, server health |
| [`content`](./content/) | ✍️ Chief Content Officer | agent.json, SOUL.md, AGENTS.md | Writing, copywriting, social media, content publishing |
| [`research`](./research/) | 🔬 Chief Research Officer | agent.json, SOUL.md, AGENTS.md | Deep research, academic papers, intelligence gathering |
| [`finance`](./finance/) | 💰 Chief Financial Officer | agent.json, SOUL.md, AGENTS.md | Accounting, P&L analysis, cost optimization, financial modeling |
| [`market`](./market/) | 📢 Chief Marketing Officer | agent.json, SOUL.md, AGENTS.md | SEO, advertising, growth strategy, channel optimization |
| [`pm`](./pm/) | 📋 Chief Project Officer | agent.json, SOUL.md, AGENTS.md | Project planning, task decomposition, quality assurance |
| [`law`](./law/) | ⚖️ Chief Legal Officer | agent.json, AGENTS.md | Contract review, compliance, legal advisory |
| [`product`](./product/) | 🎨 Chief Product Officer | agent.json, SOUL.md, AGENTS.md | Product design, competitor analysis, UX strategy |
| [`sales`](./sales/) | 🤝 Chief Sales Officer | agent.json, SOUL.md, AGENTS.md | Lead generation, business development, customer analysis |
| [`shrimp-coach`](./shrimp-coach/) | 🦐 Shrimp Coach | agent.json, SOUL.md, AGENTS.md | Specialized coaching agent |

## File Structure

Each agent folder contains:

```
agents/<id>/
├── agent.json    # Core config: model, skills, telegram bot, system prompt
├── SOUL.md       # Personality, values, communication style (optional)
├── AGENTS.md     # Team awareness — who are my colleagues (optional)
└── USER.md       # User context — who am I serving (optional)
```

## How to Use

```bash
# 1. Copy an agent template
cp -r agents/code ~/.openclaw/agents/mycode

# 2. Edit agent.json — set your API keys, model, bot token
vim ~/.openclaw/agents/mycode/agent.json

# 3. Customize SOUL.md for personality
vim ~/.openclaw/agents/mycode/SOUL.md

# 4. Restart OpenClaw
openclaw gateway restart
```

## Customization Tips

- **Model**: Change `models.json` to use any provider (Claude, GPT, Gemini, GLM, Kimi, etc.)
- **Skills**: Add/remove skills in `agent.json` → `skills` array
- **Personality**: Edit `SOUL.md` to define tone, expertise, communication style
- **Team Awareness**: Edit `AGENTS.md` so agents know who to collaborate with
