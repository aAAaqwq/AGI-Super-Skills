---
name: ship-tauri-python-sidecar
description: Build and release Tauri apps with a Python sidecar. Use for WebView shells, PyInstaller bundles, version sync, installers, CI releases, lifecycle bugs, signing, or updates.
---

# Ship Tauri Python Sidecar

Build the desktop shell and backend as one lifecycle-managed product. Treat a generated installer as an intermediate artifact; completion requires an installed-app startup and shutdown proof.

## Workflow

1. **Map the runtime topology.** Record the Tauri process, sidecar process tree, loopback API, frontend entry point, writable data root, required external runtimes, and shutdown owner.
2. **Freeze one version.** Select one canonical version and synchronize it across the backend, Tauri config, Cargo package, JavaScript package, installer name, update manifest, and release tag.
3. **Define the sidecar contract.** Give the sidecar a deterministic binary name and target-triple filename. Define its command-line dispatch, readiness endpoint, dynamic-port discovery, stdout encoding, data directory, and parent-death behavior.
4. **Constrain the shell.** Keep capabilities minimal, bind backend HTTP only to loopback, define CSP deliberately, and avoid exposing arbitrary shell execution to frontend code.
5. **Create one build entry point.** Let local builds and CI call the same script. Build dependencies, sidecar, icons, Tauri binary, installer, and SHA-256 in a fixed order. Fail on a missing or implausibly small artifact.
6. **Validate in layers.** Run unit and contract tests, sidecar CLI smoke tests, Tauri-to-sidecar handshake tests, process cleanup tests, installer structure checks, and a silent-install real startup test.
7. **Release by channel.** Separate macOS and Windows tags, artifacts, manifests, secrets, signing credentials, and rollback procedures. Never let a tag for one platform update the other platform's channel.
8. **Report evidence.** Record version, commit, runner, produced artifact, hash, startup endpoint, shutdown result, signing state, and known external prerequisites.

## Non-negotiable gates

- Do not declare success from `tauri build` alone.
- Do not infer readiness from a process name; connect to the loopback endpoint owned by the listening sidecar process.
- Account for one-file packagers that create parent and child processes with the same executable name.
- Close the shell and prove all sidecar descendants exit. Treat leftovers as a release failure.
- Keep user data outside the installation directory and preserve it across upgrades.
- Never commit signing certificates or publishing secrets. Inject them only in the release environment.
- Publish a checksum and preserve the exact build provenance.

## Decision points

- Prefer an external sidecar when the backend has a mature independent runtime or CLI surface.
- Prefer an embedded Rust implementation only when eliminating the second runtime outweighs migration risk.
- Embed a WebView runtime bootstrapper when target machines cannot be assumed to have it; document installer-size impact.
- Use per-user installation unless machine-wide installation is a product requirement with an elevation plan.

## References

- Read [release-contract.md](references/release-contract.md) when implementing or reviewing the build, CI, installer, signing, or update path.
- Read [project-evidence.md](references/project-evidence.md) when applying the lessons extracted from this repository.
