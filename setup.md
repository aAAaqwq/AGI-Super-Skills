# Setup, verification, and recovery

This guide covers the generic workspace installer. The curated Codex-native package is separate; follow [`.codex/INDEX.md`](./.codex/INDEX.md) for that distribution.

## Prerequisites

- Bash and standard Unix tools.
- Node.js for reading the canonical team manifest.
- npm and Python 3 for repository tests and validation.
- Git when the installer must fetch a repository. A local `--source` avoids that fetch.
- Write permission for the selected `--destination`.
- A supported AI harness configured separately. The installer does not configure models, credentials, or provider accounts.

OpenClaw CLI commands are legacy and optional. Codex, Claude Code, Cursor, Gemini, and Kimi have different extension models; repository metadata does not imply feature parity.

## 1. Inspect a trusted checkout

```bash
git clone --depth 1 --branch main https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team
git rev-parse HEAD
```

Record the revision, inspect `install.sh`, and review the selected agent and skill directories before applying changes.

## 2. Preview

Preview is the default. Use an explicit destination so the proposed write locations are easy to audit.

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace solo-founder
```

Other selectors are `content-creator`, `quant-trader`, `full-team`, or one agent ID such as `ceo`. A second positional agent ID filters a starter kit.

Preview may print an optional legacy OpenClaw warning. It should list planned agents and finish by asking you to re-run with `--apply`.

## 3. Apply after review

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace --apply solo-founder
```

The installer creates `workspace-<agent>/` directories beneath the destination. It copies supported persona files and selected skill directories without replacing existing paths.

Because existing files are preserved, repeated runs are not an upgrade mechanism for modified files. Review differences and merge intentionally.

## 4. Verify

```bash
find /path/to/review-workspace -maxdepth 2 -type f -name 'AGENTS.md' -print
find /path/to/review-workspace -maxdepth 3 -type f -name 'SKILL.md' -print
npm test
npm run validate
```

Expected kit workspaces:

| Kit | Expected directories |
|---|---|
| `solo-founder` | `workspace-ceo`, `workspace-pe`, `workspace-cco` |
| `content-creator` | `workspace-cco`, `workspace-cdo`, `workspace-cmo` |
| `quant-trader` | `workspace-cqo`, `workspace-cdo`, `workspace-cfo` |

Inspect the installed `SOUL.md`, `AGENTS.md`, `TOOLS.md`, and skills before trusting them. External recommendations are informational and are not bundled by the installer.

## Codex-native package

The Codex distribution is under `plugins/agi-super-team-codex/` and registered by `.agents/plugins/marketplace.json`. It does not use `install.sh` or the starter-kit mapping.

Follow the commands and safe sync procedure in [the Codex package index](./.codex/INDEX.md). Agent sync previews first, backs up differing files, and requires explicit application.

## Updates

Fetch the `main` branch, inspect the diff, run repository checks, then preview the installer again:

```bash
git fetch origin main
git diff --stat HEAD..origin/main
git diff HEAD..origin/main -- install.sh agents skills starter-kits
```

Do not blindly pull and apply when local workspace files contain customizations. The installer intentionally preserves those files.

## Recovery

If preview is wrong, stop and correct `--source`, `--destination`, or the kit selector; preview writes nothing.

If an apply is interrupted, stop and inspect the destination before rerunning it. Confirm the exact destination and any staging or backup state, then move uncertain new workspaces aside for review.

If apply reports a missing required skill, do not substitute an unrelated skill. Confirm the checkout is complete and run `npm run validate` before retrying.

Never paste credentials into repository files or command output. Configure providers through the chosen harness and keep secrets outside the project checkout.
