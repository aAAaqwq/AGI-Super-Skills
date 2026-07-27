# Project evidence: Tauri and sidecar delivery

## Evidence baseline

- Main baseline reviewed: `origin/main` at `401ad9c`.
- Windows native-automation branch reviewed: `codex/win-native-uia-1.1.7` at `526abba`.

## Primary sources

- `docs/打包发布-windows-tauri.md`: product topology and single build entry point.
- `packaging/build-tauri-windows.ps1`: version synchronization, PyInstaller sidecar, target-triple copy, icon generation, NSIS build, and hash output.
- `tauri/src-tauri/tauri.conf.json`: external binary, CSP, WebView bootstrapper, icons, and current-user installer.
- `tauri/src-tauri/src/main.rs`: shell-to-sidecar lifecycle and readiness behavior.
- `.github/workflows/release-windows.yml`: platform tag, smoke tests, silent installation, real startup, cleanup, release, and update publication.
- `tests/test_tauri_packaging.py`: static bundle contracts.

## Reusable lessons

1. A single local/CI build script prevents two release paths from drifting.
2. PyInstaller one-file mode may expose two same-name processes; find the listener rather than selecting the first process.
3. A Tauri build is not enough: the project caught lifecycle defects only by launching the shell, reaching the backend, closing the shell, and checking for orphan sidecars.
4. Platform tags and update manifests must remain independent even when source code shares `main`.
5. Documentation can lag branch reality. The main Tauri document still describes an older Windows automation prerequisite, while the Windows branch replaces it with native UIA. Reconcile release prerequisites against the code and target branch before publishing.
6. Keep build tools out of the user runtime. The installed product should not require Python, Node.js, or Rust unless explicitly designed that way.
