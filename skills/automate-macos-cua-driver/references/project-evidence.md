# Project evidence: macOS cua-driver automation

## Evidence baseline

- Main baseline reviewed: `origin/main` at `401ad9c` (`mac-v1.0.80`).
- The latest main commit restores the attachment flow for cua-driver 0.12.3 and is the authoritative macOS comparison point.

## Primary sources

- `app/cua_daemon.py`: daemon discovery, app launch, readiness, and compatibility environment.
- `app/platform/cua_compat.py`: request/response normalization and platform boundary.
- `scripts/cua_collect.py`: AX/page/input split, identity chain, preview lifecycle, file acquisition, and session cleanup.
- `scripts/cua_chat_loop.py`: AX history, contenteditable input, readback, and send verification.
- `scripts/boss_click_buheshi.py`: foreground activation, hover-dependent controls, and post-state checks.
- `scripts/build_dmg.sh`: packaged runtime and bundle mutation constraints.
- `tests/test_cua_daemon.py`, `tests/test_resume_identity_chain.py`, and `tests/test_app_shell_bundle_integrity.py`: regression evidence.

## Reusable lessons

1. A driver upgrade can preserve AX while changing page-mutation behavior. Pin and probe capabilities instead of treating “daemon ready” as “all tools ready.”
2. LaunchServices and direct CLI startup can inherit different environments and TCC identities. Test the actual packaged launch path.
3. A content fingerprint may legitimately change because the click adds a system message. Verify stable ownership fields independently from mutable content-version anchors.
4. Bridge refusal is an unknown state, not “preview absent.” This distinction prevents clicks behind stale overlays.
5. Visible business actions need a validated foreground delivery path; DOM evidence can locate a target without dispatching the action itself.
6. End sessions on every exit path. Stale sessions can leave browser windows hidden, moved, or bound to obsolete state.
7. Signed application bundles must not write runtime bytecode into their bundled standard library or resources.
