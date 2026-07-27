# Tauri + Python sidecar release contract

## Runtime contract

Define these facts before editing build files:

| Concern | Required decision |
|---|---|
| Process ownership | Which process starts and terminates the sidecar and its descendants |
| Readiness | A loopback endpoint or explicit IPC handshake, not a fixed sleep |
| Port | Dynamic or reserved; if dynamic, how the shell discovers it |
| Writable state | Per-user application data directory, never the signed install tree |
| Logging | UTF-8, flush behavior, rotation, and support-bundle location |
| Updates | Platform-specific manifest, artifact, hash, and rollback |
| External runtime | WebView, browser, driver, model service, or OS permission prerequisites |

## Build-order checklist

1. Validate the requested semantic version.
2. Update every version-bearing file deterministically.
3. Install dependencies from lockfiles.
4. Build the sidecar with an explicit entry point and hidden-import/resource contract.
5. Rename/copy the sidecar using Tauri's target-triple convention.
6. Generate icons from one source asset.
7. Build the Tauri target and installer.
8. Copy the final artifact to a stable distribution directory.
9. Calculate SHA-256 and emit machine-readable artifact metadata.

Do not silently mutate source versions during an ordinary test run. Version mutation belongs to the release build and must appear in the release diff or happen in a disposable checkout.

## Validation ladder

### Static and unit

- Parse Tauri, Cargo, and package metadata.
- Assert external binary names and capabilities.
- Assert CSP and loopback-only backend binding.
- Exercise sidecar command dispatch with `--help` or a no-side-effect health command.

### Built binary

- Start the sidecar and locate the actual listener, including one-file parent/child layouts.
- Call a health/auth endpoint and validate a version field.
- Stop the process tree and assert no descendant remains.

### Shell integration

- Start the Tauri executable.
- Wait on the sidecar endpoint with a bounded retry loop.
- Close the Tauri window gracefully, then assert sidecar cleanup.
- Force-kill only as test cleanup after recording failure.

### Installed artifact

- Install into a temporary explicit directory.
- Verify shell and sidecar files exist.
- Launch from the installed path, not the build tree.
- Verify readiness, data-root behavior, shutdown, and uninstall/upgrade policy.

## Release gates

- Use immutable action versions or commit SHAs for sensitive publishing steps.
- Restrict release permissions to the publishing job.
- Require platform-specific tags such as `win-v*` and `mac-v*`.
- Separate manual CI artifacts from public releases.
- Fail a tagged release when required publishing credentials are absent.
- Add code signing before external distribution; document unsigned behavior without presenting it as production-ready.
- Keep a prior known-good installer and manifest for rollback.
