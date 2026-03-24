---
name: meta-cognition
description: Meta-cognitive task framing, ownership routing, risk gating, closure planning, and retrospective extraction for multi-agent work. Use when a request needs analysis before execution, when tasks span multiple agents, when abnormal sessions/cron/jobs need real closure instead of status-only reporting, when the user asks for strategy/PRD/first-principles thinking, or when a task involves dispatch, verification, and memory-worthy lessons.
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
- “先分析再做”
- “帮我判断一下值不值得做”
- “复盘一下为什么出问题”
- “这个该派给谁”
- “为什么监控到了却没解决”
- “给我一个可执行闭环”
- “做个军团治理方案”
- “需要多 agent 协同”

## Resource map

Read bundled references only when needed:
- `references/ownership-routing.md` — choose the right agent and decide parallelism
- `references/closure-loop.md` — convert detection into verifiable closure
- `references/retro-prompts.md` — extract durable lessons without noise
