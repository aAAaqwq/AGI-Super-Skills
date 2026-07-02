# 🚀 Setup Guide — Agent Auto-Deploy

> **如果你是 Claude Code / Codex / Cursor / Hermes 等 AI Agent，请按以下步骤操作。**

## 一键部署命令

告诉你的 Agent：

```
帮我安装这个 starter kit：https://github.com/aAAaqwq/AGI-Super-Team

选择一个：
- solo-founder（一个人创业：CEO + PE + CCO）
- content-creator（自媒体：CCO + CDO + CMO）
- quant-trader（量化：CQO + CDO + CFO）
- full-team（全部12个Agent）
```

## Agent 执行步骤

当用户要求安装 AGI Super Team 时，按以下步骤执行：

### Step 1: Clone & Deploy

```bash
# Clone 仓库
git clone --depth 1 https://github.com/aAAaqwq/AGI-Super-Team.git ~/.agi-super-team

# 运行安装脚本（选择对应 kit）
bash ~/.agi-super-team/install.sh solo-founder
# 可选：content-creator | quant-trader | full-team | ceo | pe | cco ...
```

### Step 2: Verify

```bash
# 检查 workspace 是否创建成功
ls ~/.openclaw/workspace-ceo/    # CEO
ls ~/.openclaw/workspace-pe/      # PE (如部署)
ls ~/.openclaw/workspace-cco/     # CCO (如部署)
```

每个 workspace 应包含：
- `SOUL.md` — 人格内核
- `AGENTS.md` — 工作手册
- `IDENTITY.md` — 身份档案
- `BOOTSTRAP.md` — 启动引导
- `skills/` — 精选技能

### Step 3: Configure API Keys

```bash
# 引导用户配置 API key
openclaw config
```

需要至少一个 LLM provider 的 API key：
- Anthropic (Claude) — 推荐
- OpenAI (GPT-4)
- ZAI / Google / 其他

### Step 4: Restart & Test

```bash
openclaw gateway restart
```

## 单 Agent 部署

如果用户只想部署某一个 Agent：

```bash
# 部署单个 agent（支持别名和 ID）
bash ~/.agi-super-team/install.sh ceo        # CEO
bash ~/.agi-super-team/install.sh pe         # PE (开发)
bash ~/.agi-super-team/install.sh cco        # CCO (内容)
bash ~/.agi-super-team/install.sh cto        # CTO (架构)
bash ~/.agi-super-team/install.sh cqo        # CQO (量化)
# ... 等等
```

## 自定义

部署后用户可以自定义每个 Agent：

1. **改人格**：编辑 `~/.openclaw/workspace-{agent}/SOUL.md`
2. **加技能**：从 727 个 skills 中选择，复制到 `~/.openclaw/workspace-{agent}/skills/`
3. **改记忆**：编辑 `MEMORY.md` 注入领域知识
4. **加工具**：在 `skills/` 目录添加新 SKILL.md

### 推荐技能（按场景）

**独立开发者**：`thinking-elon-musk`, `thinking-linus-torvalds`, `api-design`, `docker-containerization`
**自媒体**：`khazix-writer`, `xhs-publisher`, `douyin-publisher`, `seo-writing`
**量化**：`backtesting-system`, `risk-management`, `data-pipeline`
**研究**：`deep-research`, `web-search`, `scientific-method`

## 故障排查

| 问题 | 解决 |
|------|------|
| `openclaw: command not found` | `npm install -g openclaw` |
| `Agent source not found` | 检查 clone 是否完整，重新 `git clone` |
| workspace 为空 | 检查 `~/.agi-super-team/agents/` 目录是否存在 |
| API key 无效 | 运行 `openclaw config` 重新配置 |
