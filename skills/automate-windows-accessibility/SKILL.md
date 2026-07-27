---
name: automate-windows-accessibility
description: Design, implement, diagnose, and validate Windows desktop or browser automation using native UI Automation, Win32 input, and optional CDP evidence. Use when locating accessibility elements, clicking virtualized lists, handling DPI or multiple monitors, controlling real Chrome sessions, preventing stale-element or stale-panel errors, downloading authenticated files, or replacing an unstable cross-platform automation driver on Windows.
---

# Automate Windows Accessibility

Separate perception, identity, action, and proof. A successful API return is never proof that the target application changed state.

## Architecture

Use this default split:

```text
Element semantics and geometry  -> native UI Automation
Stable web identity and DOM evidence -> read-only CDP
Mouse, keyboard, wheel, drag -> Win32 SendInput
Post-action truth -> fresh UIA/CDP/application state
Window, process, DPI, screenshot -> Win32 APIs
```

Keep business code behind a platform-neutral adapter. Do not leak HWNDs, screen coordinates, UIA runtime IDs, or CDP session objects into domain models.

## Workflow

1. **Establish the window.** Resolve the owning process and top-level HWND. Reject minimized, hidden, zero-sized, or sentinel off-screen windows. Restore and foreground only when an action needs it.
2. **Take a bounded snapshot.** Read UIA through a worker or supervisor with a hard timeout. Include control type, accessible name, automation ID, class, rectangle, enabled/off-screen state, parent relation, and supported patterns.
3. **Bind by semantics and context.** Match exact role/type plus normalized label, then bind through parent/child context to the intended card, row, panel, or dialog. Treat indexes and runtime tokens as snapshot-local.
4. **Make the target visible.** If virtualized or off-screen, scroll the correct container, wait, and take a new snapshot. Never click coordinates from the pre-scroll snapshot.
5. **Compute screen coordinates once.** Use Per-Monitor DPI awareness and virtual-desktop coordinates. Do not rescale an already physical screen origin. Support negative monitor coordinates.
6. **Deliver the action.** Prefer `SendInput` for Chromium/web content. Use UIA patterns for native controls when their semantics are reliable, but still verify the result.
7. **Verify with fresh evidence.** Poll for a target-specific state transition: selected identity, dialog appearance/disappearance, field value, button state, URL, attachment, or content signature.
8. **Retry safely.** Reacquire the element before each retry. Bound attempts, capture diagnostics, and fail closed when identity or state is ambiguous.
9. **Clean up.** Ensure UIA workers, process job objects, input state, previews, and foreground changes are recovered on normal exit, exception, timeout, or interruption.

## Safety rules

- Use CDP as evidence by default; do not mix a DOM click with a path intended to behave like OS input.
- Bind downloads and persisted records to a stable identity, operation source, preview evidence, and file hash.
- Stop on login, challenge, verification, or unexpected navigation pages. Never automate challenge completion.
- Do not claim `SendInput` is indistinguishable from physical hardware. Windows can mark injected input.
- Do not continue reading the previous panel after a click that produced no confirmed state change.
- Do not treat an empty UIA tree as proof that the page contains no target.
- Use pacing to absorb rendering races, not to promise evasion of platform detection.

## Diagnostics

Capture the fresh UIA snapshot, matched element metadata, window state, DPI/monitor map, intended and delivered coordinates, before/after identity, URL, retry reason, and screenshot. Redact personal or secret data before sharing diagnostics.

## References

- Read [automation-contract.md](references/automation-contract.md) for element, coordinate, action, identity, worker, and test contracts.
- Read [project-evidence.md](references/project-evidence.md) for the repository's native UIA migration evidence and recurring failure modes.
