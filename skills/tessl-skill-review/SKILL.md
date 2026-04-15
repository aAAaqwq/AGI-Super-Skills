---
name: tessl-skill-review
description: Evaluate, score, and review an Agent Skill or SKILL.md using Tessl as the primary evaluator. Use when asked to measure skill quality, score a skill, review a skill against best practices, compare before/after skill revisions, or generate structured improvement feedback for a skill directory or SKILL.md file.
---

# Tessl Skill Review

Use Tessl as the default scoring engine for skill quality review.

This skill is for **measuring quality**, not just giving vibes. Prefer Tessl-backed review first, then add your own judgment on top.

## Primary use cases

Use this skill when asked to:
- score a skill
- evaluate a `SKILL.md`
- review a skill against best practices
- compare two versions of a skill
- decide whether a skill is ready to publish
- find weaknesses in skill triggering, structure, or instructions

## Core workflow

### 1) Identify the review target

Accept either:
- a skill directory containing `SKILL.md`
- a direct path to `SKILL.md`
- a repo path with one or more skills to audit

If the request is ambiguous, clarify which skill or directory to score.

### 2) Prefer Tessl review first

If Tessl CLI is available, start with:

```bash
tessl skill review <path>
```

Useful examples:

```bash
tessl skill review ~/.openclaw/skills/meta-cognition
tessl skill review ./skills/work-to-skill
tessl skill review ./skills/some-skill/SKILL.md
```

If the exact CLI surface has drifted, inspect:

```bash
tessl --help
tessl skill --help
```

If Tessl is not installed, either:

1. install it with:

```bash
curl -fsSL https://get.tessl.io | sh
```

2. or use the bundled helper:

```bash
scripts/review.sh <path>
```

The helper script will detect whether Tessl exists, print the install command if missing, and run `tessl skill review <path>` when available.

### 3) Extract a structured scorecard

From Tessl review output, capture at least:
- overall score
- strongest areas
- weakest areas
- trigger/description quality issues
- instruction clarity issues
- missing examples / weak workflow guidance
- context bloat or redundancy risks
- publish-readiness judgment

If Tessl returns category scores, preserve them verbatim where possible.

## Manual fallback rubric

If Tessl cannot be installed or executed, do a manual review using this scoring rubric.

Score each dimension from **1-5**:
- **Trigger clarity**: does the description clearly say what the skill does and when to use it?
- **Workflow executability**: can another agent follow the steps without guessing?
- **Context efficiency**: is the skill lean, or does it waste context?
- **Reusability**: does it avoid hidden tribal knowledge and local-only assumptions?
- **Safety**: does it properly constrain risky or irreversible actions?

Convert to a 100-point score:

```text
Total = (sum of 5 dimension scores / 25) * 100
```

Verdict bands:
- **90-100**: publish-ready
- **75-89**: strong, but improve a few areas
- **60-74**: useful, but needs substantial revision
- **<60**: not ready

Always state clearly whether the score came from **Tessl** or from the **manual fallback rubric**.

## Secondary workflow: scenario-based evaluation

When the user wants deeper validation, go beyond `skill review` and run scenario evals.

Use Tessl scenario tooling when the question is not just “is this well-written?” but “does this skill actually improve agent performance?”

Preferred flow:

```bash
tessl scenario generate <path>
tessl scenario run <path-or-scenario>
```

Use scenario evals for:
- regression checks after editing a skill
- comparing two versions of a skill
- checking whether extra context actually helps
- judging real task success rather than surface quality only

## What to look for in your analysis

After Tessl output, add your own judgment across these dimensions:

### 1. Trigger quality
- Is the frontmatter description specific enough to trigger reliably?
- Does it say both **what the skill does** and **when to use it**?
- Is it too vague, too generic, or too narrow?

### 2. Workflow quality
- Are the steps executable?
- Does the skill guide the agent through decisions, not just dump information?
- Are fragile steps sufficiently constrained?

### 3. Context efficiency
- Is the body concise enough?
- Does it duplicate obvious model knowledge?
- Should detailed material move into references instead of bloating `SKILL.md`?

### 4. Reusability
- Would another agent instance be able to use this without extra tribal knowledge?
- Are assumptions, prerequisites, and inputs explicit?

### 5. Safety and overreach
- Does the skill push the agent toward risky or irreversible actions without proper checks?
- Are approval boundaries and destructive actions handled clearly?

## Output format

Use this output shape unless the user asks for another format:

```markdown
## Tessl Skill Review
- Target:
- Tessl overall score:
- Verdict: ready / close / needs work / not publishable yet

## Strengths
- ...

## Weaknesses
- ...

## High-impact fixes
1. ...
2. ...
3. ...

## Suggested rewrite areas
- frontmatter:
- workflow:
- examples:
- references/scripts:

## Final recommendation
- ...
```

## Publishing / PR use

When reviewing skills for a PR or public registry submission:
- use Tessl score as an input, not the only decision-maker
- call out any mismatch between score and real-world usefulness
- flag private-environment coupling, hardcoded paths, secret handling, or weak public readability

## Anti-patterns

Do not:
- give a score without actually running Tessl when Tessl is available
- confuse “nice writing” with “effective agent behavior”
- accept a high-level skill that has no actionable workflow
- ignore bloated context just because the prose sounds polished
- assume a skill is good only because it is long

## Quick command checklist

```bash
# install if needed
curl -fsSL https://get.tessl.io | sh

# or use the bundled helper
scripts/review.sh <path>

# inspect CLI if unsure
tessl --help
tessl skill --help

# basic quality review
tessl skill review <path>

# deeper evals when needed
tessl scenario generate <path>
tessl scenario run <path-or-scenario>
```

## Trigger phrases

- “测一下这个 skill 的评分”
- “帮我评估这个 SKILL.md”
- “这个 skill 质量怎么样”
- “用 Tessl 跑一下 skill review”
- “compare these two skill versions”
- “is this skill publish-ready?”
- “score this skill”
- “review this skill against best practices”
