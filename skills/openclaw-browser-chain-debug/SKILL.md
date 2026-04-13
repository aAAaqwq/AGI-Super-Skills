---
name: openclaw-browser-chain-debug
description: "Diagnose OpenClaw browser control failures including browser start timeouts, Chrome CDP startup failures, missing DISPLAY, browser profile launch issues, and gateway/browser environment mismatches. Use when browser automation, browser-based cron jobs, or profile openclaw fails to start, times out, or returns Request was aborted after browser steps. Also use when deciding whether a task should run with a profile browser versus an attach browser: prefer profile for unattended automation and recurring jobs; prefer attach when a human's already-open logged-in tab or manual cooperation is required."
---

# OpenClaw Browser Chain Debug

Use this skill to debug the OpenClaw browser control chain systematically before changing config.

## First decision: profile browser vs attach browser

Choose the browser mode before debugging deeper, because many "timeout" issues are really mode mismatches.

### Use **profile browser** when

Use `profile=openclaw` or another profile browser for:
- unattended automation
- cron jobs
- recurring checks
- stable repeatable flows
- flows that should not depend on the user's currently open tab
- cases where OpenClaw should own the browser lifecycle

Default automation choice:
- `profile=openclaw` for bot-owned automation

Why:
- isolated session
- reproducible state
- safer for long-running automation
- easier to reason about failures

### Use **attach / user browser** when

Use attach-style control (`profile=user` or current user browser attach flow) for:
- taking over a page the human already opened
- using existing cookies/logins in the user's live browser
- cases where the human may need to click, scan, approve, or solve CAPTCHA
- login recovery and manual collaboration flows
- debugging a page that only works in the current visible user session

Why:
- reuses existing logged-in state
- supports human-in-the-loop actions
- avoids rebuilding fragile login state in automation profiles

### Common mistake

Do **not** force `profile=openclaw` for flows that really require:
- the human's already-logged-in tab
- manual scan/approval
- extension relay / attach behavior

Do **not** force attach/user-tab control for:
- cron jobs
- unattended background refresh tasks
- large recurring inspection loops

## Quick workflow

1. Confirm the symptom.
2. Check whether the chosen browser mode is correct.
3. Check browser runtime state.
4. Check gateway/service environment.
5. Read the exact browser error from logs.
6. Classify the failure.
7. Apply the smallest fix that matches the failure mode.
8. Re-test with the minimal browser start/status path.

## Step 1: Confirm the symptom

Gather the exact failure text first. Common triggers:
- `browser start(profile=openclaw)` timed out
- `Failed to start Chrome CDP`
- `Missing X server or $DISPLAY`
- browser-dependent cron ended as `Request was aborted`
- `running:false` / `cdpReady:false`
- user asked for browser takeover but the automation was incorrectly routed through a profile browser

Do not guess from the top-level timeout alone.

## Step 2: Check browser runtime state

Run these first:

```bash
openclaw gateway status
openclaw status
```

Then use the browser tool or equivalent checks to inspect:
- profile name
- `running`
- `cdpReady`
- `headless`
- `noSandbox`
- detected Chrome path
- CDP port

Interpretation:
- `gateway running` + `browser running:false` usually means browser/profile launch failure, not full gateway outage.
- `running:true` + `cdpReady:false` usually means Chrome launched badly or CDP never became reachable.
- attach/user flows failing while profile flows work often means user-side browser attach/approval was never completed.

## Step 3: Check service environment

Inspect the environment seen by the gateway/service, not just your interactive shell.

Key variables:
- `DISPLAY`
- `XDG_SESSION_TYPE`
- `WAYLAND_DISPLAY`
- optionally `XAUTHORITY`

Also check whether the host actually has a display server:

```bash
printf 'DISPLAY=%s\nXDG_SESSION_TYPE=%s\nWAYLAND_DISPLAY=%s\n' "$DISPLAY" "$XDG_SESSION_TYPE" "$WAYLAND_DISPLAY"
ps -ef | grep -E '[X]org|[X]wayland|[X]vfb'
```

Important pattern:
- If Xorg exists on the host but the gateway environment has empty `DISPLAY`, the issue is usually **service/session environment mismatch**, not “no GUI exists anywhere”.

## Step 4: Read logs before fixing

Search the OpenClaw log for browser-specific evidence:

```bash
grep -nE 'browser|CDP|DISPLAY|X server|18800|timeout' /tmp/openclaw/openclaw-$(date +%F).log | tail -n 120
```

Prioritize the deepest concrete error over generic timeout wrappers.

## Step 5: Classify the failure

### A. Missing display / GUI mismatch

Signals:
- `Missing X server or $DISPLAY`
- `headless:false`
- service env has empty `DISPLAY`
- host may still have Xorg running

Root cause:
- OpenClaw is trying to launch headed Chrome from a service that is not attached to a desktop session.

Preferred fix:
- Prefer **headless** mode for cron/profile automation.

Alternative fix:
- If headed mode is required, wire the gateway service into the desktop session environment (`DISPLAY`, `XAUTHORITY`, etc.). This is more fragile.

### B. Sandbox/container launch problem

Signals:
- Chrome mentions sandbox failure
- running in container/root-like environment
- error suggests trying `browser.noSandbox: true`

Fix:
- Only if the environment truly requires it, enable `browser.noSandbox: true` after checking config schema first.

### C. Gateway alive, browser lane stuck

Signals:
- gateway RPC probe OK
- browser tool repeatedly times out
- logs show lane congestion, repeated browser failures, or cascading cron timeouts

Fix direction:
- reduce browser concurrency
- stagger browser-heavy cron jobs
- add explicit degraded-mode alerts instead of letting the whole cron hang

### D. Wrong browser mode selected

Signals:
- a cron/unattended flow was pointed at attach/user browser
- a human-cooperative flow was pointed at `profile=openclaw`
- login/captcha/approval depended on user presence but automation expected fully unattended success

Fix:
- move unattended jobs to profile browser
- move human-in-the-loop / existing-tab tasks to attach or `profile=user`
- update the prompt/skill so the mode choice is explicit up front

## Step 6: Repair policy

Use the smallest repair that matches the evidence.

Recommended order:
1. Confirm the browser mode is correct: profile vs attach.
2. Prefer headless browser for unattended automation.
3. Only wire DISPLAY/XAUTHORITY if a visible browser is truly needed.
4. Only change `noSandbox` when sandbox/root/container evidence points there.
5. After browser is stable, harden browser-dependent cron jobs with degraded mode and explicit alerts.

## Step 7: Re-test minimally

After any fix, re-test in this order:
1. gateway status
2. browser status
3. browser start/status for `openclaw` or the intended mode
4. one minimal browser-dependent task
5. only then re-run the full cron/job

Do not jump straight to the largest cron as the first verification step.

## Browser-dependent cron hardening

If a cron depends on browser:
- use profile browser by default, not attach/user-tab control
- persist partial state before browser work
- send explicit `browser down` alerts when browser is unavailable
- avoid long per-platform fan-out before a final summary
- degrade to latest-known state when safe, but mark it stale
- avoid one browser failure making the whole job silent

## Local lesson from this host

On this host, one confirmed root cause was:
- Xorg existed on the machine
- but the OpenClaw systemd service had empty `DISPLAY` / `XDG_SESSION_TYPE` / `WAYLAND_DISPLAY`
- and the `openclaw` profile was non-headless
- which caused Chrome CDP startup failure and browser timeouts

For the exact checklist and interpretation, read `references/checklist.md`.
