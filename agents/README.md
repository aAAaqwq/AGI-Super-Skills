# 👥 Agents — AGI Super Team C-Suite

> [← Back to main README](../README.md)

Ready-to-deploy agent configurations for building your own AI-native company.
Each agent is embodied with a **spirit mentor** — a real-world archetype that shapes their personality, decision-making, and communication style.

## 🏛️ Team Roster (C-Suite)

| ID | Role | Avatar | Spirit Mentor | Files | Description |
|----|------|--------|---------------|-------|-------------|
| [`main`](./main/) | 👑 CEO | 小a | **Elon Musk** | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 战略决策中枢 — 任务调度、质量终审、跨部门协调 |
| [`code`](./code/) | ⚡ CTO | Jensen | **Jensen Huang**, Kelsey Hightower | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 技术架构决策 — 后端/前端/运维/全栈开发 |
| [`product`](./product/) | 🎨 CPO | 小product | **Steve Jobs** | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 产品设计 — 竞品分析、UX策略、品牌DNA |
| [`quant`](./quant/) | 📈 CQO | Simons | **Jim Simons** | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 量化交易 — 市场分析、策略回测、套利 |
| [`market`](./market/) | 📣 CMO | Ogilvy | **David Ogilvy** | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 市场营销 — SEO、广告投放、增长策略 |
| [`finance`](./finance/) | 💰 CFO | Buffett | **Warren Buffett** | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 财务管理 — 核算、盈亏分析、成本优化 |
| [`data`](./data/) | 📊 CDO | Silver | **Nate Silver** | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 数据工程 — 爬虫、ETL、数据分析 |
| [`content`](./content/) | ✍️ CCO | Ives | **Jony Ive**, MrBeast | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 创意内容 — 极简设计+病毒传播 |
| [`law`](./law/) | ⚖️ CLO | Dershowitz | **Alan Dershowitz** | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 法务合规 — 合同审核、法律文书 |
| [`research`](./research/) | 🔬 CRO | Feynman | **Richard Feynman** | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 深度调研 — 学术论文、情报收集、技术选型 |
| [`sales`](./sales/) | 🤝 CSO | Dell | **Michael Dell** | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 销售拓客 — 商业分析、客户开发 |
| [`ops`](./ops/) | ⚙️ COO | Grove | **Andy Grove** | agent.json, SOUL.md, AGENTS.md, TOOLS.md | 运维管理 — 系统监控、部署、效率优化 |
| [`shrimp-coach`](./shrimp-coach/) | 🦐 Shrimp Coach | — | — | agent.json, SOUL.md, AGENTS.md | Specialized coaching agent |

## 📁 File Structure

Each agent folder contains:

```
agents/<id>/
├── agent.json    # Core config: model, skills, telegram bot, system prompt
├── SOUL.md       # 灵魂配置 — 人格、价值观、沟通风格、决策框架、精神导师
├── AGENTS.md     # 团队认知 — 角色定义、核心职责、协作网络、工作规范
├── TOOLS.md      # 工具笔记 — 常用路径、推荐技能、API索引
└── USER.md       # 用户画像 — 服务对象背景 (optional)
```

### SOUL.md 设计哲学

每个 SOUL.md 基于 **精神导师** 构建：

1. **身份** — Agent 的名字、角色、精神导师
2. **人格特质** — 从导师身上提炼的 3-5 个核心性格维度
3. **沟通风格** — 如何说话、如何汇报、如何反馈
4. **决策框架** — 面对选择时的思维模型和优先级
5. **核心能力** — 该角色的专业技能栈
6. **反模式** — 明确列出不该做的事
7. **协作偏好** — 和谁协作、怎么协作
8. **工作哲学** — 一句信条 + 3-5 条工作原则

## 🚀 How to Use

```bash
# 1. Copy an agent template
cp -r agents/code ~/.openclaw/agents/mycode

# 2. Edit agent.json — set your API keys, model, bot token
vim ~/.openclaw/agents/mycode/agent.json

# 3. Customize SOUL.md for personality (or keep the spirit mentor!)
vim ~/.openclaw/agents/mycode/SOUL.md

# 4. Restart OpenClaw
openclaw gateway restart
```

## 🎨 Customization Tips

- **Model**: Change `agent.json` → `model` to use any provider (Claude, GPT, Gemini, GLM, Kimi, etc.)
- **Skills**: Add/remove skills in `agent.json` → `skills` array
- **Personality**: Edit `SOUL.md` to define tone, expertise, communication style
- **Team Awareness**: Edit `AGENTS.md` so agents know who to collaborate with
- **Spirit Mentor**: Replace the mentor name to shift the agent's entire personality

## 🔄 Last Sync

- **Date**: 2026-04-14
- **Source**: `~/.openclaw/workspace-{ROLE}/` → `agents/{id}/`
- **Files synced**: SOUL.md, AGENTS.md, TOOLS.md (12 agents)
