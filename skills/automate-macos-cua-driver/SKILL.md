---
name: automate-macos-cua-driver
description: Design, implement, diagnose, and validate macOS GUI or browser automation built on cua-driver, Accessibility AX trees, page bridges, and foreground input. Use when starting or packaging the driver daemon, handling macOS permissions, locating AX elements, clicking Chrome content, entering text, managing sessions, downloading authenticated files, or fixing automation that reports success without a verified UI state change.
---

# Automate macOS with cua-driver

Treat cua-driver as a versioned transport with explicit capabilities. Keep AX perception, page-level evidence, foreground input, and business-state verification separate.

## Workflow

1. **Pin the runtime contract.** Record macOS, Chrome, cua-driver, packaged app, and target-site versions. Run driver health and tool-description checks; do not assume a capability from an older version.
2. **Establish permissions.** Verify Accessibility and Screen Recording for the actual executable or signed app identity. Verify Chrome automation/page-bridge prerequisites only when the workflow needs them.
3. **Start one daemon.** Prefer the packaged driver app when required for TCC identity. Pass only documented or deliberately version-pinned environment flags. Wait for readiness with a bounded probe.
4. **Own one session.** Use a unique session name, close stale same-name sessions before starting, and register idempotent cleanup for normal exit, signals, exceptions, and timeouts.
5. **Find and activate the target window.** Match application and window identity, reject hidden or invalid geometry, and foreground only immediately before actions that require it.
6. **Read fresh AX state.** Locate elements by role, label, ancestry, and current frame. Treat element indexes as snapshot-local and reacquire after scrolling or navigation.
7. **Choose the correct action path.** Use the page bridge for DOM-only identity or authenticated in-page fetches when supported. Use foreground driver mouse/keyboard delivery for visible business actions that must behave like user input.
8. **Verify the business result.** Poll a new AX/page snapshot for the intended state transition. Driver success, `verified`, or an accepted event is not enough.
9. **Protect identity and files.** Bind selected object, visible panel, action source, preview, downloaded file, hash, and persisted owner. Fail closed on disagreement.
10. **Recover cleanly.** Close previews, clear draft input when appropriate, end the session, and confirm the driver did not hide or strand the browser window.

## Capability policy

- Feature-detect `page`, JavaScript mutation, background/foreground delivery, screenshot, and AX-tree behavior per driver version.
- Keep version-specific escape hatches near daemon startup and cover them with tests. Do not scatter environment assumptions through business scripts.
- Prefer a page bridge for DOM identifiers and same-session authenticated fetches; prefer visible foreground input for user-facing business actions.
- Represent unknown state separately from false. A bridge error is not evidence that a preview, dialog, or element is absent.

## Failure policy

- Reacquire stale elements; never retry an old index blindly.
- Stop sensitive processing when the active candidate/object identity changes.
- Do not consume content behind a preview whose presence cannot be determined.
- Distinguish permission denial, daemon unavailable, tool unsupported, bridge refusal, target not found, input delivery failure, and no post-state change.
- Capture redacted AX state, window metadata, driver response path, before/after identity, and screenshot for bounded failures.

## References

- Read [driver-contract.md](references/driver-contract.md) for daemon, permission, session, action, verification, and packaging checklists.
- Read [project-evidence.md](references/project-evidence.md) for the macOS implementation lessons extracted from this repository.
