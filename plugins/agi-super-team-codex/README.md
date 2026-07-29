# AGI Super Team for Codex

This directory is the curated Codex plugin implementation. It is intentionally smaller than the root skills library.

Use the human-facing [Codex package index](../../.codex/INDEX.md) for installation, included roles, update policy, and current evidence status.

After installing the plugin, use `$agi-super-team-sync` or run its installer directly:

```bash
python3 skills/agi-super-team-sync/scripts/install_codex_team.py --list-teams
python3 skills/agi-super-team-sync/scripts/install_codex_team.py --global-ceo --all-teams
python3 skills/agi-super-team-sync/scripts/install_codex_team.py --global-ceo --all-teams --install
```

The installer manages only its marked block in the global Codex `AGENTS.md` and the selected `ast-*` Agent TOMLs. Preview is the default; unrelated guidance and Agents are preserved.

The plugin manifest proves package structure only. Do not label client loading or task behavior Verified until a revision-matched receipt passes in a current Codex client.
