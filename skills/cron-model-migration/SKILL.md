---
name: cron-model-migration
description: 'Safely change models for OpenClaw cron jobs without leaving behind session/model mismatch errors. Use when creating or editing cron jobs with `payload.model`, when moving a job between models/providers, when diagnosing `LiveSessionModelSwitchError`, or when deciding whether a cron should run in `sessionTarget: "isolated"`, `"current"`, `"main"`, or a custom persistent session.'
---

# Cron Model Migration

## Overview

Use this skill when a cron job needs a model change or when cron runs fail after a model change. The goal is simple: avoid reusing a session that is already bound to a different model.

## Core rule

Prefer **`sessionTarget: "isolated"`** for cron jobs that set `payload.model`.

Why:
- isolated jobs run dedicated agent turns instead of sharing the main session
- isolated runs are the safest place to override model/thinking
- persistent/shared sessions are where model-switch residue shows up most often

If a cron does **not** need shared conversation history, keep it isolated.

## Decision tree

### Case 1 — New cron job with a specific model

Create it as:
- `payload.kind = "agentTurn"`
- `sessionTarget = "isolated"`
- `payload.model = <target-model>`

Do **not** bind it to `current` or `session:xxx` unless you explicitly need persistent context across runs.

### Case 2 — Existing isolated cron, same session pattern, just changing model

Safe workflow:
1. Confirm the job is not actively running.
2. Disable the job.
3. Update `payload.model`.
4. Restart Gateway if the job has recently been running or already failed with a model-switch error.
5. Re-enable the job.
6. Force-run once and inspect the result.

If it still throws `LiveSessionModelSwitchError`, stop trying to patch it in place. Rebuild the job fresh.

### Case 3 — Existing cron bound to `current` or `session:xxx`

Treat this as **high risk** for model residue.

Best practice:
- create a **new job** instead of editing the old one in place
- move it to `sessionTarget: "isolated"` unless persistent context is truly required
- if persistent context is required, use a **new custom session id** instead of reusing the old one

Do not reuse a persistent session and expect model changes to be clean.

### Case 4 — Main-session cron

Avoid model overrides on main-session jobs unless there is a strong reason.

Why:
- main-session jobs share context with the main agent session
- changing model there can shift the shared session unexpectedly
- OpenClaw docs recommend model overrides primarily for isolated jobs

If the task needs a different model, split it into an isolated cron instead.

## Recommended migration workflow

Use this sequence for production changes:

1. **Inspect**
   - confirm `sessionTarget`
   - confirm `payload.kind`
   - confirm current `payload.model`
   - check recent run failures

2. **Classify**
   - isolated + stateless → update in place is usually fine
   - current/custom/main → prefer rebuild

3. **Apply**
   - small change: disable → update → restart → enable → force-run
   - risky change or prior switch error: create a new isolated job with the new model

4. **Verify**
   - run exactly once with `cron.run`
   - verify the run completed, not merely enqueued
   - verify delivery/output still works

5. **Cut over**
   - only remove the old job after the replacement job succeeds

## Anti-patterns

Avoid these:
- changing `payload.model` and immediately force-running repeatedly
- reusing `sessionTarget: "current"` for jobs that need model churn
- editing a persistent `session:xxx` job without changing the backing session id
- assuming `cron.run` enqueue success means the agent turn succeeded
- debugging only the prompt while ignoring session binding

## Troubleshooting `LiveSessionModelSwitchError`

When you see:
- `LiveSessionModelSwitchError: Live session model switch requested: ...`

Assume one of these first:
1. the job is reusing a live or persistent session already bound to another model
2. the job was edited in place after prior runs left session state behind
3. the job is using `current`, `main`, or a custom persistent session where override behavior is unsafe

Response order:
1. inspect job config
2. confirm `sessionTarget`
3. confirm whether the run is isolated or persistent
4. restart Gateway if stale execution state is plausible
5. if still failing, replace the job with a fresh isolated one

## Minimal safe templates

### Stateless background analysis

Use:
- `sessionTarget: "isolated"`
- `payload.kind: "agentTurn"`
- explicit `payload.model`
- optional `delivery.mode: "announce"` or `"none"`

### Persistent weekly summary that truly needs memory

Use:
- `sessionTarget: "session:<new-id>"`
- `payload.kind: "agentTurn"`
- explicit `payload.model`
- accept that model changes later should usually mean **creating a new session id/job**

## Practical rule of thumb

If you need to ask “can I safely switch this cron’s model in place?”, the default answer is:
- **yes** for isolated/stateless jobs, with one controlled validation run
- **no** for shared or persistent jobs; rebuild instead
