---
name: market-nightly-evolution
description: Nightly market evolution report — overnight market analysis and strategy prep
---

# Market Nightly Evolution Skill

> 用于小market agent夜间深度进化 cron 任务。隔离 session 工作空间 ≠ ~/clawd/market/，必须使用绝对路径。

## 触发

由 cron `5dc81e53-6e20-4ec9-b0de-93de83768e43` 调用（agentId=market, sessionTarget=isolated）

## 重要路径约束

**工作空间警告**：isolated session 的 workspace 是 `~/.openclaw/agents/market/`，而不是 `~/clawd/market/`。
- ✅ 用绝对路径: `/home/aa/clawd/market/market.md`
- ✅ 用绝对路径: `/home/aa/clawd/market/memory/YYYY-MM-DD.md`
- ❌ 禁止用相对路径（如 `market.md`、`memory/xxx.md`）

## 执行步骤

### 00:30 轮 — 今日总结 + 反思复盘

1. 读取今日 market 群聊记录（如果有）
2. 读取 `/home/aa/clawd/market/MEMORY.md` 和 `/home/aa/clawd/market/memory/YYYY-MM-DD.md`
3. 总结今日关键活动/学习/决策
4. 深度反思：本周是否有真实用户交互？技能是否有实际进展？
5. 写入 `/home/aa/clawd/market/memory/YYYY-MM-DD.md`（追加新章节）

### 07:30 轮 — 明日规划

1. 读取今日 memory 文件
2. 制定次日重点任务和优先级
3. 更新 `/home/aa/clawd/market/MEMORY.md` 中相关章节

## 文件路径（必须用绝对路径）

- Memory 日志: `/home/aa/clawd/market/memory/YYYY-MM-DD.md`
- 主记忆: `/home/aa/clawd/market/MEMORY.md`
- 市场报告: `/home/aa/clawd/market/market.md`

## 工具使用规则

- 更新 MEMORY.md 或 memory/*.md 时，使用 write 工具整体覆写，不要使用 edit 工具
- edit 工具在 isolated session 可能因路径解析问题失败
- 如果必须用 edit，确保每个 edits[].oldText 指向文件中不重叠的独立区域
