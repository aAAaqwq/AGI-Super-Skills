# Browser Chain Debug Checklist

## Minimal evidence set

Collect these before proposing a fix:

1. `openclaw gateway status`
2. `openclaw status`
3. browser status for profile `openclaw`
4. service-shell environment values:
   - `DISPLAY`
   - `XDG_SESSION_TYPE`
   - `WAYLAND_DISPLAY`
5. whether Xorg/Wayland/Xvfb exists on the host
6. last 100-150 browser-related log lines

## Fast interpretation table

### Case 1
- gateway running: yes
- browser running: no
- log: `Missing X server or $DISPLAY`
- profile headless: false

Interpretation:
- Headed Chrome launch attempted from service without display session.

Best fix:
- Switch browser automation to headless if possible.

### Case 2
- gateway running: yes
- browser running: no
- log mentions sandbox/root/container

Interpretation:
- Chrome sandbox startup issue.

Best fix:
- Consider `browser.noSandbox: true`, but only after verifying schema and environment need.

### Case 3
- gateway running: yes
- browser intermittent timeouts
- many browser-heavy cron jobs overlap

Interpretation:
- contention / lane congestion / brittle long-running chain.

Best fix:
- stagger jobs, shorten each run, add degraded mode.

## Cron hardening pattern

For browser-heavy cron jobs:

1. Save partial state before browser navigation.
2. Send immediate failure alert on browser unavailability.
3. Continue with degraded summary when possible.
4. Avoid many per-platform messages if one summary works.
5. Mark reused browser state as stale, not fresh.

## Known local example

Observed on 2026-03-23:
- `browser start(profile=openclaw)` timed out at top level.
- Deep log showed `Failed to start Chrome CDP on port 18800`.
- Chrome stderr showed `Missing X server or $DISPLAY`.
- Host still had Xorg running.
- Gateway/systemd service environment had empty `DISPLAY`, `XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`.
- Therefore root cause was environment mismatch, not total gateway outage.
