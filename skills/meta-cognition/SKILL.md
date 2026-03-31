---
name: meta-cognition
description: Meta-cognitive framing for analyze-before-doing, ownership routing, risk gating, minimum-closure planning, and retrospective extraction in multi-agent work. Use when the user says 先分析再做 / 先别动手 / 先判断 / 先定方案, when work spans multiple agents or needs dispatch/orchestration, when CEO-style delegation or group command requires owner+deadline+closure, when abnormal sessions/cron/jobs/runs need real follow-through instead of status-only reporting, or when a task needs strategy, PRD, first-principles thinking, verification, and postmortem/retro.
author: Daniel Li
---

# Meta-Cognition

Use this skill to turn a vague request, anomaly, or project into a governed execution loop.

This skill is for **judgment before action** and **closure after action**. It is especially useful for CEO-style coordination where the main risk is not lack of tools, but wrong framing, wrong ownership, missing verification, or shallow status reporting.

## Core protocol

For any non-trivial task, produce these six sections before major execution:

1. **问题本质 / Problem Essence**
2. **责任归属 / Ownership Routing**
3. **风险等级 / Risk Gate**
4. **最小闭环 / Minimum Closure**
5. **执行动作 / Action Plan**
6. **验证与复盘 / Verification & Retro**

If the user asks for a fast answer, compress the six sections into short bullets instead of skipping them.

## When to apply strict mode

Use full strict mode when any of the following is true:
- The request affects money, production systems, accounts, auth, deployments, or public output.
- The task spans multiple agents or requires dispatch.
- The user explicitly says “先分析再做”, “别急着开发”, “复盘一下”, or asks for strategy.
- You detect stale sessions, zombie jobs, aborted runs, or cron drift that needs resolution.
- You are about to claim a task is done and fresh verification matters.

In strict mode, do not jump from detection straight to execution. Frame → route → gate → act → verify.

## Step 1 — Problem Essence

Rewrite the request into the real problem.

Answer:
- What is the surface request?
- What is the underlying business/operational problem?
- What would count as success in one sentence?
- What is still unknown?

Rules:
- Strip hype and vague labels.
- Prefer operational language over abstract buzzwords.
- If the request is probably misframed, say so directly.

## Step 2 — Ownership Routing

Decide who should do the work.

Answer:
- Which agent owns the core capability?
- Which supporting agents, if any, should assist?
- Should the CEO/main session coordinate only, or also execute?
- Can independent sub-tasks run in parallel?

Rules:
- CEO should prefer routing and quality control over doing specialized execution.
- Route by core capability, not by convenience.
- If a task crosses functions, split it into separate deliverables.

For detailed routing heuristics, read `references/ownership-routing.md`.

## Step 3 — Risk Gate

Assign a risk level before acting.

Use three levels:
- **P0 / High risk** — money movement, prod changes, auth, data loss, public posting, destructive actions
- **P1 / Medium risk** — important but reversible config/code/content changes
- **P2 / Low risk** — read-only analysis, drafts, internal notes, low-impact summaries

For every task, state:
- Risk level
- Main failure mode
- Whether user confirmation is required
- What should be protected from overreach

Rules:
- For high-risk work, default conservative.
- “Can do” is not enough; ask whether it should be done now.

## Step 4 — Minimum Closure

Define the smallest end-to-end result that counts as actually finished.

Examples:
- Not “cron checked”, but “cron updated, effective model confirmed, drift explained”.
- Not “agent notified”, but “agent received, responded, and delivered or was escalated”.
- Not “API built”, but “fresh tests passed and real request returned required fields”.

State:
- Deliverable
- Verification method
- Evidence expected
- What remains out of scope

For closure patterns, read `references/closure-loop.md`.

## Step 5 — Action Plan

Only now decide what to do.

Use one of four modes:
- **Act now** — enough clarity, low/moderate risk, tools available
- **Dispatch** — another agent should own execution
- **Ask first** — critical missing context or approval needed
- **Defer** — low ROI or blocked

When dispatching:
- Give a clear objective
- Specify output location/format
- Specify how completion should be reported
- Define timeout/escalation expectations

If useful, use this structure:
- Objective
- Owner
- Inputs
- Output
- Deadline / next check
- Escalation path

## Step 6 — Verification & Retro

Before saying “done”, check:
- What was verified just now?
- What evidence supports the claim?
- What is still assumed rather than proven?
- What lesson should become memory, SOP, skill, or cron?

Never collapse “looks good” into “done”.

If the task produced a reusable lesson, explicitly propose one of:
- Update memory
- Update skill
- Update SOP/checklist
- Update cron/monitoring
- No durable lesson

For retro extraction prompts, read `references/retro-prompts.md`.

## Default output template

Use this template unless the user asks for a different format:

```markdown
## 1. 问题本质
- 表层需求：
- 真问题：
- 成功标准：
- 未知项：

## 2. 责任归属
- 主负责：
- 协同：
- CEO 是否亲自执行：
- 是否并行：

## 3. 风险等级
- Level：P0 / P1 / P2
- 失败模式：
- 是否需确认：

## 4. 最小闭环
- 交付物：
- 验证方式：
- 完成证据：
- 当前不做：

## 5. 执行动作
- 模式：Act / Dispatch / Ask / Defer
- 下一步：

## 6. 验证与复盘
- 已验证：
- 未验证：
- 可沉淀项：
```

## Anti-patterns

Do not do these:
- Jump straight into execution when the request is still ambiguous.
- Treat status reporting as problem resolution.
- Keep work in the CEO session when a specialist agent should own it.
- Claim completion without fresh evidence.
- Inflate low-confidence guesses into decisions.
- Leave anomalies as “known issue” without owner, next step, or closure condition.

## Trigger phrases

This skill is a strong match for prompts like:

### 中文高频触发
- “先分析再做” / “先别动手” / “先别急着写代码”
- “先判断一下” / “先定方案” / “先想清楚再做”
- “帮我拆一下这事” / “这个事情怎么收口” / “给个最小闭环”
- “这个该派给谁” / “谁负责” / “你来协调一下” / “拉多 agent 一起做”
- “CEO 指令” / “CEO 派发” / “军团任务” / “帮我调度一下” / “安排下去并盯闭环”
- “异常怎么处理” / “为什么又炸了” / “为什么监控到了却没解决” / “把这个事故复盘一下” / “给我复盘”
- “别只报状态” / “我要结果，不要过程” / “给我一个能验收的版本”
- “先看风险” / “值不值得做” / “要不要现在做” / “先评估 ROI / 风险”
- “帮我定 owner / deadline / 验收标准” / “这个事情怎么推进” / “下一步谁来做”

### English triggers
- “analyze first, then do” / “think first” / “frame this before acting”
- “who should own this?” / “route this to the right agent” / “orchestrate this”
- “give me a closure plan” / “what is the minimum end-to-end closure?”
- “don’t just give status, close the loop” / “turn this into a verified outcome”
- “postmortem this” / “retro this” / “why did this fail?”
- “dispatch this across agents” / “multi-agent coordination” / “CEO delegation”

### 群聊/命令式说法
- “你先别做，先判断”
- “先出分析框架再执行”
- “去查清楚再汇报”
- “先给结论、风险、owner、下一步”
- “盯到闭环，不要只催办”
- “这事给我复盘并沉淀 SOP / memory / skill”

## Resource map

Read bundled references only when needed:
- `references/ownership-routing.md` — choose the right agent and decide parallelism
- `references/closure-loop.md` — convert detection into verifiable closure
- `references/retro-prompts.md` — extract durable lessons without noise
