# Release Process

This project uses a tag-driven release model with a single source of truth for versions.

## Single Source of Truth

- `VERSION` is authoritative.
- `pyproject.toml` and all `backtester/crates/*/Cargo.toml` versions must match `VERSION`.
- `ws_sidecar/Cargo.toml` and `hub/Cargo.toml` should also be kept in sync (not currently enforced by CI).
- Release tags must match the same version in `vX.Y.Z` format.

Enforcement:

- Local and CI checks: `tools/release/check_versions.sh`
- CI guardrail: `.github/workflows/version-governance.yml`

## Standard Release Flow

1. Prepare a version bump in a dedicated worktree branch:
   - `tools/release/set_version.sh 0.1.1`
2. Open an atomic PR targeting `master`, review, then merge.
3. Cut an annotated tag from the merged commit:
   - `git tag -a v0.1.1 <commit-sha> -m "Release 0.1.1"`
   - `git push origin v0.1.1`
4. GitHub Actions builds assets and publishes the release automatically via `.github/workflows/release-on-tag.yml`.

## Release Assets

The release workflow publishes:

- `mei-backtester-linux-x86_64-vX.Y.Z`
- `config-examples-vX.Y.Z.tar.gz`
- `systemd-examples-vX.Y.Z.tar.gz`
- `release-manifest-vX.Y.Z.txt`
- `SHA256SUMS`

You can build the same asset set locally:

```bash
tools/release/build_assets.sh 0.1.1
```

Default local output path:

- `artifacts/releases/vX.Y.Z/`

This keeps root-level housekeeping clean and avoids ad-hoc release files in the repository root.
