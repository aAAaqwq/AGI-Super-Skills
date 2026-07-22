# CLAUDE.md: AGI Super Team

This file is repository context for coding agents. It is not an installation script or proof of harness compatibility.

## Product model

- `skills/` contains canonical physical skill entrypoints. Catalog inclusion proves structure, not behavior.
- `agents/` contains generic role packs defined by `config/team-manifest.json`.
- `starter-kits/` selects small, outcome-oriented combinations of those roles.
- `plugins/agi-super-team-codex/` is a separately curated Codex distribution.
- `catalog/` is generated discovery output and never an inventory source.

Read [ARCHITECTURE.md](./ARCHITECTURE.md) before changing boundaries or sources of truth.

## Installation requests

Route users to the maintained guide for their surface:

- Generic workspace: [setup.md](./setup.md)
- Codex package: [.codex/INDEX.md](./.codex/INDEX.md)
- Other manifests: [harness compatibility](./docs/guides/harness-compatibility.html)

Never run legacy OpenClaw commands, restart gateways, write credentials, or install the full skills library merely because the user says “install.” Preview is the default; `--apply` must be explicit.

## Repository contracts

```bash
npm test
npm run validate -- --warnings-as-errors
npm run check:skills
npm run check:skill-quality
git diff --check
```

Preserve user changes, avoid machine-local paths and skill symlinks, and do not promote a distribution or outcome to Verified without a revision-matched receipt.
