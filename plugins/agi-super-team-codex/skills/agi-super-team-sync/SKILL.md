---
name: agi-super-team-sync
description: Preview, install, or update AGI Super Team in Codex. Use when the user asks to inject the Musk CEO into the global main agent, list or install a C-suite team, or sync bundled specialist agents.
---

# AGI Super Team Sync

## Overview

Install AGI Super Team in two explicit layers:

1. A managed Musk CEO block in the user's global `AGENTS.md`, making the current Codex parent the CEO coordinator in every repository.
2. One or more outcome Teams backed by the generated `ast-*` C-suite leaf agents.

The installer preserves content outside its managed block, never deletes unrelated agents, leaves `config.toml` unchanged, previews by default, and backs up replaced files.

## Workflow

1. Resolve `scripts/install_codex_team.py` relative to the absolute directory containing this `SKILL.md`. Do not assume the current working directory is the Skill directory.
2. List the available Teams when scope is unclear:

   ```bash
   python3 "<absolute-skill-directory>/scripts/install_codex_team.py" --list-teams
   ```

3. Preview the smallest requested installation. For the global CEO and all outcome Teams:

   ```bash
   python3 "<absolute-skill-directory>/scripts/install_codex_team.py" --global-ceo --all-teams
   ```

   For one Team, replace `--all-teams` with `--team solo-founder` or another listed Team ID.

4. Summarize additions, updates, unchanged files, destination, and any `AGENTS.override.md` warning.
5. Because the user must explicitly request installation, only then append `--install` to the exact previewed command.
6. Report the backup directory when files were replaced. Tell the user to start a new Codex task; Codex loads global guidance and personal Agent TOMLs at task start.

To sync every bundled specialist Agent rather than an outcome Team, use the legacy all-Agent path:

```bash
python3 "<absolute-skill-directory>/scripts/sync_codex_agents.py"
python3 "<absolute-skill-directory>/scripts/sync_codex_agents.py" --install
```

## Safety Rules

- Never copy credentials, conversation databases, memory stores, `config.toml`, or unrelated local backups.
- Never delete destination files. Unrelated agents remain untouched.
- Preserve all content outside the `AGI-SUPER-TEAM:CEO` managed markers in global `AGENTS.md`.
- Refuse malformed markers, symlinked destinations, unsafe Codex homes, incomplete Team payloads, and unknown Team IDs.
- Keep the preview as the default. Use `--install` only when the user has authorized installation or synchronization.
- A custom destination may be supplied with `--codex-home`; validate it before use.
- Do not enable automatic hooks, daemons, or background memory capture.

## Configuration

This Skill deliberately leaves `~/.codex/config.toml` unchanged. The eight parent-led outcome Teams work with depth 1. For wider Team runs, recommend reviewing settings such as:

```toml
[agents]
max_threads = 4
max_depth = 1
job_max_runtime_seconds = 1800
interrupt_message = true
```

Explain that these values are recommendations, not requirements. Preserve existing settings and let the user decide before editing them.
