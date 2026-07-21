---
name: agi-super-team-sync
description: Safely preview or install the specialist Codex agent TOMLs bundled with the AGI Super Team plugin. Use when the user asks to install, update, synchronize, or audit AGI Super Team agents in their personal Codex configuration.
---

# AGI Super Team Sync

## Overview

Synchronize the plugin's curated agent payload into the user's personal Codex agent directory. The script is non-destructive: it does not delete unrelated agents or edit `config.toml`, and it backs up every differing destination file before replacement.

## Workflow

1. Resolve `scripts/sync_codex_agents.py` relative to the absolute directory containing this `SKILL.md`. Do not assume the user's current working directory is the skill directory.
2. Run a preview first:

   ```bash
   python3 "<absolute-skill-directory>/scripts/sync_codex_agents.py"
   ```

3. Summarize the planned additions, updates, unchanged files, and destination.
4. Only when the user asked to install or sync, apply the plan:

   ```bash
   python3 "<absolute-skill-directory>/scripts/sync_codex_agents.py" --install
   ```

5. Report the backup directory when files were replaced. Tell the user to start a new Codex task so newly installed roles are discovered.

## Safety Rules

- Never copy credentials, conversation databases, memory stores, `config.toml`, or local backups.
- Never delete destination files. Unrelated agents remain untouched.
- Refuse a source payload containing symlinks or files other than top-level `.toml` agent definitions.
- Keep the preview as the default. Use `--install` only when the user has authorized installation or synchronization.
- A custom destination may be supplied with `--codex-home`; validate it before use.
- Do not enable automatic hooks, daemons, or background memory capture.

## Configuration

This skill deliberately leaves `~/.codex/config.toml` unchanged. If the user wants native parallelism, recommend reviewing and adding settings such as:

```toml
[agents]
max_threads = 4
max_depth = 1
job_max_runtime_seconds = 1800
interrupt_message = true
```

Explain that these values are recommendations, not requirements. Preserve existing settings and let the user decide before editing them.
