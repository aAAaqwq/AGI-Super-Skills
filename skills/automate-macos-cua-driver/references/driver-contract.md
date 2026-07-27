# cua-driver macOS contract

## Preflight

- Resolve the exact driver binary or app bundle.
- Record `cua-driver --version` and tool descriptions.
- Verify daemon readiness separately from binary presence.
- Verify Accessibility and Screen Recording for the actual runtime identity.
- If a page bridge is used, run a read-only probe before any workflow mutation.
- Confirm the target Chrome profile is logged in and the expected page is open.

## Daemon lifecycle

Prefer this sequence:

1. Detect an already-ready daemon and reuse it.
2. Otherwise launch the packaged app/daemon with a minimal environment.
3. Poll a bounded readiness command.
4. On failure, report process state and logs; do not leave repeated daemons.

Treat compatibility flags as pinned implementation details. Add a regression test that asserts how the app launcher or CLI receives each required flag.

## Session lifecycle

- Generate a process-specific session name.
- End an old same-name session before creating a new one.
- Make `end_session` idempotent and best effort.
- Register cleanup with `finally`, `atexit`, and relevant signal handlers.
- Verify browser visibility/window geometry after abnormal shutdown when the driver can manage windows.

## Element and action rules

- Match exact AX role and normalized label before using an index.
- Bind repeated labels through ancestry or a stable DOM/page identity.
- Scroll targets into view, then reacquire their current index/frame.
- Translate screenshot/window coordinates using one documented coordinate space.
- For user-facing browser actions, require the expected foreground delivery path and reject unknown delivery modes.
- For text entry, write, read back, and only then send/submit.

## Post-state rules

Define a specific receipt for every action, for example:

- target row becomes selected and panel identity changes;
- dialog appears or disappears;
- button becomes disabled or changes text;
- input contains the exact normalized text;
- a new own-message node appears;
- a unique preview opens and later closes;
- a downloaded body passes format and ownership checks.

Use tri-state observations (`true`, `false`, `unknown`) when the probe can fail. Unknown must not be treated as absence.

## Packaging and permissions

- Keep the bundle identifier and signing identity stable across updates so TCC grants remain meaningful.
- Embed the intended driver binary/app and verify bundle integrity.
- Do not write bytecode or mutable runtime files into a signed read-only bundle.
- Run a clean-machine permission walkthrough and an upgrade walkthrough.
- Document which actions require Chrome's Apple-events JavaScript setting and which use only Accessibility/input.

## Acceptance matrix

- Fresh install with no permissions.
- Permissions granted to terminal versus packaged app.
- Driver restart and stale session cleanup.
- Chrome refresh/navigation invalidating AX indexes.
- Duplicate labels and virtualized lists.
- Page bridge unsupported or mutation refused.
- Input delivered but no state change.
- Preview state unknown and stale preview cleanup.
- Ctrl-C, timeout, task stop, and app quit.
- Signed package upgrade retaining permissions and data.
