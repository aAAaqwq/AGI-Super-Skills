# Project evidence: native Windows automation

## Evidence baseline

- Current Windows branch reviewed: `codex/win-native-uia-1.1.7` at `526abba`.
- Native migration starts at commit `6d08724` and subsequent stabilization commits through `526abba`.
- Main comparison baseline: `origin/main` at `401ad9c`.

## Primary sources on the Windows branch

- `docs/windows-native-uia-backend-plan.md`: architecture, migration status, real-machine results, and acceptance matrix.
- `app/platform/native_windows_uia.py`: supervised native UIA backend and compatibility surface.
- `app/platform/win32_input.py`: Per-Monitor DPI, virtual desktop coordinates, `SendInput`, wheel, keyboard, and cursor motion.
- `app/platform/win_ui.py`: semantic element lookup, contact parsing, scrolling, and state checks.
- `app/windows_cdp.py`: local real-Chrome bootstrap and CDP evidence channel without added packages.
- `scripts/build_windows_uia_worker.py`: native worker build integration.
- `tests/test_native_windows_uia.py`, `tests/test_win_ui.py`, and Windows compatibility suites: UIA, Win32 input, DPI, and business contract evidence.

## Reusable failure lessons

1. Driver-level UIA calls can hang even when native UIA is healthy; supervise provider calls with process isolation and hard timeouts.
2. A Chromium `InvokePattern` return is not a reliable web-click receipt. Use OS input and verify application state.
3. Whole-card accessible names can include a descendant button label. Require the exact button control type and exact label.
4. React virtual lists invalidate old positions and tokens after scrolling. Re-snapshot after every scroll.
5. UIA does not expose DOM-only identifiers. Use an independent evidence channel for stable UID, but do not join UID and names from different moments by ordinal position.
6. Sticky bars and message cards can mirror one business event. Count unique message scopes, not raw repeated text leaves.
7. A file download is not complete until identity, preview, file body, SHA-256, and persisted owner agree.
8. DPI conversion bugs often come from scaling the virtual screen origin twice. Scale offsets, preserve physical origins.
9. Challenge pages must terminate the batch with a distinct reason; otherwise missing elements are misdiagnosed as click failures.
10. Process cleanup belongs to the architecture: worker job objects and parent-exit cleanup prevent orphan providers.
