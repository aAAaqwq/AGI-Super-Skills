# Distill — 高质量外部 Skills 仓库索引

> 2026-05-19 调研，24 个仓库，~3300 个 skill 文件
> 本地路径: `~/clawd/repos/distill/`

---

## Tier S — 必装

| # | 仓库 | ⭐ | Skills | 说明 |
|---|------|-----|--------|------|
| 1 | [anthropics/skills](https://github.com/anthropics/skills) | ~135K | 18 | Anthropic 官方 skills |
| 2 | [obra/superpowers](https://github.com/obra/superpowers) | ~192K | 14 | 高质量 agent 技能集 |
| 3 | [everything-claude-code](https://github.com/affaan-m/everything-claude-code) | ~182K | 773 | 🔥 最大 Claude Code skills 库 |
| 4 | [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) | ~131K | 1 | Karpathy 风格工程方法论 |
| 5 | [mattpocock/skills](https://github.com/mattpocock/skills) | ~84K | — | TypeScript/工程实践 |
| 6 | [claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | 53.6K | 9 | Claude Code 最佳实践 |

## Tier A — 高价值

| # | 仓库 | ⭐ | Skills | 说明 |
|---|------|-----|--------|------|
| 7 | [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | 43.4K | — | Awesome list，129 篇文章索引 |
| 8 | [agent-skills](https://github.com/addyosmani/agent-skills) | ~42K | 23 | Addy Osmani 的 agent 技能 |
| 9 | [awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 34.5K | 864 | 🔥 最大社区 skills 库 |
| 10 | [impeccable](https://github.com/pbakaus/impeccable) | 27.6K | 14 | 高质量工程实践 |
| 11 | [planning-with-files](https://github.com/OthmanAdi/planning-with-files) | ~20K | 17 | 文件驱动的任务规划 |
| 12 | [Understand-Anything](https://github.com/Lum1104/Understand-Anything) | ~12K | 8 | 万物理解框架 |
| 13 | [awesome-openclaw-skills](https://github.com/VoltAgent/awesome-openclaw-skills) | ~8K | — | OpenClaw 生态 skills 索引 |
| 14 | [claude-skills](https://github.com/alirezarezvani/claude-skills) | 15.4K | 721 | 🔥 大型 skills 集合 |
| 15 | [agents](https://github.com/wshobson/agents) | 18.7K | 155 | Agent 模式与工作流 |
| 16 | [claude-flow](https://github.com/ruvnet/claude-flow) | ~11K | 317 | Claude 工作流引擎 |

## Tier B — 值得关注

| # | 仓库 | ⭐ | Skills | 说明 |
|---|------|-----|--------|------|
| 17 | [awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | ~5K | — | Agent skills awesome list |
| 18 | [claude-mem](https://github.com/thedotmack/claude-mem) | ~12.8K | 18 | Claude 记忆系统 |
| 19 | [supermemory](https://github.com/supermemoryai/supermemory) | ~16.7K | 1 | 超级记忆引擎 |
| 20 | [gstack](https://github.com/garrytan/gstack) | ~97.4K | 57 | Garry Tan 技术栈 |
| 21 | [ruflo](https://github.com/ruvnet/ruflo) | ~51.4K | 317 | Claude Flow 分支 |
| 22 | [claude-code-subagents](https://github.com/0xfurai/claude-code-subagents) | ~2K | — | Sub-agent 模式集 |
| 23 | [claude-memory](https://github.com/robwhite4/claude-memory) | — | — | 记忆管理方案 |

## 特色单项

| 仓库 | ⭐ | 说明 |
|------|-----|------|
| [frontend-slides](https://github.com/zarazhangrui/frontend-slides) | 18K | 前端演示文稿生成 |

---

## Top 5 技能金矿

| 排名 | 仓库 | Skill 文件 | 去重后新增 |
|------|------|-----------|-----------|
| 🥇 | awesome-claude-skills | 864 | ~835 |
| 🥈 | everything-claude-code | 773 | ~691 |
| 🥉 | claude-skills | 721 | ~653 |
| 4 | claude-flow | 317 | ~309 |
| 5 | agents | 155 | ~137 |

---

## 快速搜索

```bash
# 搜索特定主题
find ~/clawd/repos/distill -name "SKILL.md" | xargs grep -li "docker" 2>/dev/null

# 按关键词搜索所有仓库
grep -r "kubernetes" ~/clawd/repos/distill/*/SKILL.md 2>/dev/null

# 查看某个仓库结构
find ~/clawd/repos/distill/everything-claude-code -name "SKILL.md" | head -20
```

---

*调研来源: research/github-highvalue-skills-repos-2026-05.md*
*最后更新: 2026-05-22*
