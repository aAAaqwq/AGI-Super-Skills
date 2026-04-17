---
name: claude-code-controller
description: Orchestrate Claude Code CLI as a supervised execution worker with ECC-aware context, small task rounds, active monitoring, verification gates, and failure recovery. Use when delegating coding, refactors, docs, deployment work, or repo maintenance to Claude Code instead of hand-editing. Especially useful when the operator must manage Claude Code sessions, inspect logs, verify real file changes and commits, and leverage ECC-style skills, workflows, memory, and looped execution.
---

# Claude Code Controller

Run Claude Code as an **execution worker under supervision**, not as an unsupervised black box.

## First: understand the local Claude Code / ECC environment

Treat the current environment as more than bare Claude Code.

### 1. What exists here

From the current machine and session context, Claude Code is surrounded by obvious ECC-style components such as:

- `configure-ecc`
- `claw`
- `nanoclaw-repl`
- `evomap`
- `instinct-*`
- `learn` / `evolve` / `promote`
- workflow skills like `plan`, `verify`, `loop`, `code-review`, `tdd`

Useful local interpretation:
- `loop`: run repeatedly / periodic execution / iterative operation
- `configure-ecc`: configure ECC itself

This means the environment already includes:
- a skill layer
- a memory/learning layer
- a workflow/orchestration layer
- not just raw Claude Code

The mental model is simple:

`user request -> skill match -> skill expands into structured prompt/workflow -> Claude executes by that workflow`

It is not magic. It is reusable operational packaging.

### 2. What ECC is for

ECC is not “another model”.
It is an enhancement operating layer around Claude Code.

Use this mental model:

- **Claude Code = brain**
- **ECC = hands + toolbox + memory + process orchestration**

Its purpose is to let Claude Code work in repeatable engineering loops instead of just doing ad hoc chat-style coding.

ECC-style capabilities usually help Claude Code:
- plan before coding
- split work into tasks
- coordinate multiple agents/workers
- remember project habits
- run loops
- verify results
- distill experience into instinct/skill

### 2.5. Relationship between ECC and native Claude Code

Understand the stack like this:

- **Claude Code**: the lower-level executor that can read files, edit code, run commands, and use tools
- **ECC**: the higher-level engineering framework that adds:
  - conventions
  - workflows
  - multi-agent orchestration
  - memory
  - reusable skills
  - evolutionary improvement mechanisms

ECC does not replace Claude Code.
It upgrades Claude Code from “can do work” into “can do work within a repeatable system”.

### 3. How it works in practice

#### A. Skill layer

ECC gives Claude Code many specialized skills.
Typical examples:
- `plan`: plan first
- `tdd`: test-first execution
- `code-review`: review after implementation
- `verify`: verify before claiming done
- `loop`: run repeated/iterative execution
- `configure-ecc`: configure ECC itself

So when orchestrating Claude Code, assume it may be stronger if prompted to use or respect these skills and workflows rather than being asked to freestyle everything.

#### B. Rules layer

Expect the environment to inject global engineering rules, for example:
- always answer in Chinese
- plan before implementation
- TDD discipline
- code review after writing
- security checks
- file editing restrictions in some areas

The principle is not that the model becomes magically smarter.
The principle is that rules shape the model toward stable engineering behavior.

When orchestrating Claude Code, respect the rules instead of fighting them.
Use them as hard constraints in your prompts.

#### C. Memory / instinct layer

ECC strongly values: “learn once, avoid repeating the same stupid mistake.”

Typical memory-style assets include:
- project memory
- user preferences
- validated approaches
- instinct patterns
- `learn` / `evolve` / `promote` style distillation mechanisms

The operating principle is:
1. work happens in a session
2. stable lessons are extracted
3. lessons are stored as memory / instinct
4. similar future tasks should reuse those lessons first

So the goal is not only “write code once”.
The goal is to make the agent increasingly resemble an experienced project teammate.

#### D. Orchestration layer

ECC often works best with multiple cooperating workers instead of one worker brute-forcing everything.

A task may be split into roles such as:
- planner: prepare the approach first
- tdd agent: write tests first
- implementation agent: change code
- reviewer: review the code
- verifier: run validation
- deploy/hardening specialist: handle release or production safety when relevant

The principle is simple:
- break complex work into role-based stages
- reduce pollution of the main context
- make results more stable

In plain terms: replace “one person thrashing around” with “pipeline work”.

Even when only one Claude Code CLI instance is running, think in orchestration terms:
- separate phases
- separate checks
- separate responsibilities
- explicit handoff between rounds

This mindset improves reliability.

#### E. Loop / long-running workflow layer

ECC also becomes valuable when work must repeat over time.

Examples:
- check deployment status every 5 minutes
- babysit a PR continuously
- rerun a verification flow repeatedly

The principle is straightforward:
- schedule or trigger repeated execution
- each trigger runs a prompt / skill / workflow step
- the result determines the next round

This turns Claude from “do one thing when clicked” into a semi-automatic operator on watch duty.

## Core operating mode

- Be the orchestrator.
- Let Claude Code do the concrete edits.
- Keep tasks small, explicit, and verifiable.
- Monitor every run until it clearly finishes or fails.
- Never assume success from process launch alone.
- Prefer using available ECC-style skills/workflows when relevant.

## Use this workflow

### 1. Prepare the target repo first

- Confirm the correct working directory.
- Confirm the repo name/path matches the intended long-term location.
- Inspect current state before delegation:
  - `git status --short --branch`
  - recent commits
  - key files relevant to the task
- If the task is a migration/rename, do that setup first before invoking Claude Code.

### 2. Keep each Claude Code round narrow

Prefer one round per concrete outcome.

Good rounds:
- update README + product positioning
- refactor deploy workflow only
- add nginx config + deployment docs
- fix build errors only

Bad rounds:
- “restructure the whole project, harden deployment, finish docs, and launch production”

If the work is large, split into sequential rounds.

### 3. Use deterministic Claude Code invocation

Use Claude Code in non-interactive print mode:

```bash
claude --permission-mode bypassPermissions --print '...task...'
```

Guidelines for prompts:
- State the exact repo path.
- Say whether file modification is allowed.
- State the round goal and boundaries.
- Specify required outputs:
  - changed files
  - rationale
  - validation results
  - remaining issues
- If you want a commit, say so explicitly.
- If you do **not** want destructive changes, say so explicitly.
- If ECC workflow skills are relevant, tell Claude Code to use them.

### 4. Monitor actively, not passively

After starting Claude Code in background:
- poll its process status
- check logs periodically
- do not leave it unattended for long stretches

Required monitoring rule:
- no “fire-and-forget” for important coding sessions

If output is quiet:
- poll again with a longer wait
- fetch logs
- verify whether the process still exists

### 5. Verify real work happened

Never trust the session status alone. After Claude Code exits, always verify:

```bash
git status --short --branch
git log --oneline -n 5
```

Also inspect changed files when relevant:

```bash
git diff --name-only
```

If the task requested a commit, verify that a new commit actually exists.

### 6. Treat silent exits as failures until proven otherwise

If the process disappears and you have:
- no new commit
- no changed files
- no useful summary

then treat the round as failed or incomplete.

Do not report success.
Do not guess.
Restart with a smaller, sharper task.

### 7. Recover by shrinking scope

If a Claude Code run fails, restart with a smaller unit of work.

Recovery pattern:
1. identify the smallest useful deliverable
2. relaunch Claude Code on only that deliverable
3. monitor until completion
4. verify files/commit
5. only then continue to the next round

Example split:
- Round A: README + positioning
- Round B: docs cleanup
- Round C: deployment workflow refactor
- Round D: nginx/TLS/security docs

### 8. Keep the human updated at milestones

Send short, concrete updates only when useful:
- task started
- important failure
- question/blocker
- round finished

Good update format:
- where Claude Code is running
- what this round is supposed to accomplish
- whether it is still running / failed / finished
- what changed

### 9. Prefer repo-safe verification gates

At the end of each round, ask Claude Code to run only the validations relevant to that round, such as:
- `npm run build`
- lint/test if present
- config syntax checks
- file tree sanity checks

Do not claim “done” without at least one validation step.

### 10. Deployment/security rounds need explicit checklists

For deployment-oriented work, require Claude Code to address:
- build reproducibility
- separation of server bootstrap vs routine deploy
- domain assumptions
- HTTPS/TLS assumptions
- rollback path
- post-deploy verification
- safe defaults

## Standard round template

Use this structure when drafting a new Claude Code task:

```text
Round N task for project <path>.
Modify files in-place.
Goal: <single narrow goal>.
Constraints: <what not to change>.
Deliverables:
1) <files or outputs>
2) <validation>
3) <summary>
4) <commit requirement if any>
Do not do destructive changes.
```

## Failure patterns to avoid

- Starting Claude Code and not monitoring it
- Giving one huge multi-domain task
- Reporting progress without checking git state
- Assuming output buffering means success
- Mixing project migration, product strategy, deployment hardening, and coding in one round

## Definition of done for a round

A round is done only if all are true:
- Claude Code process has clearly ended
- expected files changed
- validation ran
- results were inspected
- commit exists if requested
- remaining issues are known

If any item is missing, the round is not done.
