# 🚀 Solo Founder Starter Kit

> 一个人就是一支军队。CEO + 首席工程师 + 首席内容官，3 个 Agent 覆盖创业核心需求。

## 包含的 Agents

| Agent | 角色 | 精神导师 | 能做什么 |
|-------|------|----------|---------|
| 👑 CEO | 战略决策 + 团队协调 | Elon Musk | 第一性原理思考、任务调度、质量把控 |
| 💻 PE | 全栈开发 + DevOps | Linus Torvalds, DHH | 写代码、架构、Docker、测试、部署 |
| ✍️ CCO | 内容创作 + 病毒传播 | MrBeast, Jony Ive | 小红书/抖音/公众号发布、内容策略 |

## 一键部署

```bash
# 方式1：curl（推荐）
curl -sSL https://raw.githubusercontent.com/aAAaqwq/AGI-Super-Team/main/install.sh | bash -s -- solo-founder

# 方式2：clone 后执行
git clone https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team
./install.sh solo-founder
```

## 部署后配置

```bash
# 1. 设置 API Key（选择你的provider）
openclaw config
# 填入 API key，比如 Anthropic / OpenAI / ZAI

# 2. 重启 gateway
openclaw gateway restart

# 3. 开始使用
# CEO: 直接在配置的聊天通道跟它说话
# PE: 切换到 pe agent 或在群聊中 @它
# CCO: 切换到 cco agent
```

## 你能让他们做什么？

### CEO (战略 + 协调)
```
"帮我分析一下这个竞品"
"制定下个月的产品路线图"
"review 一下这个技术方案的可行性"
```

### PE (开发 + 工程)
```
"帮我写一个 REST API，用 FastAPI"
"给这个项目写 Dockerfile 和 docker-compose"
"review 这个 PR 的代码质量"
"写一个 Playwright E2E 测试"
```

### CCO (内容 + 传播)
```
"把这篇文章发到小红书"
"帮我写一篇关于 AI Agent 的公众号文章"
"分析一下这个账号的内容策略"
```

## 架构

```
你 (创始人)
  └── 👑 CEO (ceo) — 接收你的指令，协调 PE 和 CCO
        ├── 💻 PE — 代码、技术、部署
        └── ✍️ CCO — 内容、发布、传播
```

## 精选 Skills（已预装）

- **CEO**: team-coordinator, context-manager, healthcheck, daily-rhythm, web-search, project-planner
- **PE**: react-expert, tdd-workflow, systematic-debugging, code-review-quality, github, gh-issues, docker-containerization, deployment-automation, kubernetes-specialist, ghost-scan-code, cli-developer
- **CCO**: xhs-publisher, douyin-publisher, gzh-publisher, content-pipeline, seo-writing

## 扩展

想加更多 Agent？

```bash
# 加 CTO（架构设计）
./install.sh cto

# 加 CFO（财务）
./install.sh cfo

# 或者直接部署全部 12 个
./install.sh full-team
```

## 需要

- [OpenClaw](https://github.com/openclaw/openclaw) 已安装
- 至少一个 LLM API key（推荐 Claude / GPT-4）
- Telegram Bot（可选，用于聊天界面）
