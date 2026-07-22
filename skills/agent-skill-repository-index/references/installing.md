# Safe Skill Installation and Lifecycle

## Table of Contents

- [Choose the installation mode](#choose-the-installation-mode)
- [Preflight](#preflight)
- [Codex](#codex)
- [Claude Code and OpenClaw](#claude-code-and-openclaw)
- [Validate](#validate)
- [Update](#update)
- [Rollback or remove](#rollback-or-remove)
- [Installation receipt](#installation-receipt)

## Choose the Installation Mode

| Candidate | Action |
|---|---|
| Catalog with no runnable root skill | Do not install; search it and follow the chosen item to upstream. |
| Repository containing many skills | Select and review one subdirectory. Never expose the repository root globally. |
| Passive single skill with compatible metadata | Link the reviewed directory or use the client's native installer. |
| Skill requiring Codex-specific wording or tools | Copy to a personal Codex skill root, normalize, and record provenance. |
| Plugin, hook suite, MCP server, daemon, memory system, browser profile, deployer, or connector | Keep quarantined until the user explicitly authorizes those runtime effects. |

## Preflight

1. Resolve the exact upstream URL and local source directory.
2. Confirm `git remote get-url origin`, commit, license, and worktree status.
3. Read the complete candidate directory and identify every executable or external action.
4. Compare its name and trigger semantics with installed skills.
5. Select an explicit destination and verify it is absent. Never overwrite an existing file, directory, or symlink.
6. Obtain explicit approval for any quarantined behavior; ordinary passive local skill installation needs no extra approval when the user already requested it.

## Codex

Prefer these methods in order:

1. Use the built-in `$skill-installer` for a supported GitHub repository or subpath.
2. For a clean reviewed local source, create one symlink in the documented shared personal skill root, represented here as `<agent-skills-dir>/<skill-name>`.
3. When adaptation is required, copy the complete skill into `<codex-home>/skills/<skill-name>`, normalize frontmatter to only `name` and `description`, and generate `agents/openai.yaml`.
4. For project-only behavior, use the project's documented `.agents/skills/<skill-name>` location instead of a personal-global target.

Before linking, resolve both source and target to explicit absolute paths. Refuse if the target already exists. Link only the directory containing the reviewed `SKILL.md`.

## Claude Code and OpenClaw

- Prefer the upstream repository's documented marketplace or plugin installation when the candidate is a plugin rather than a plain skill.
- For a plain Claude Code skill, use the client-documented `<claude-config>/skills/<skill-name>` location only after adapting unsupported tool names when necessary.
- For a plain OpenClaw skill, use the documented `<openclaw-config>/skills/<skill-name>` location and review OpenClaw-specific hooks, services, and credentials separately.
- Do not copy one client's hooks, permissions, slash commands, or tool metadata literally into another client.

## Validate

For Codex-compatible skills, run:

```bash
python3 <codex-home>/skills/.system/skill-creator/scripts/quick_validate.py <installed-skill-dir>
```

Also verify:

- every referenced relative resource resolves;
- folder name equals frontmatter `name`;
- the global or project link resolves to the intended source;
- one representative request triggers the skill;
- one nearby but out-of-scope request does not trigger it;
- no duplicate name or substantially overlapping description was introduced.

## Update

1. Inspect local changes before fetching. Preserve dirty clones.
2. Fetch the upstream and compare commits.
3. Fast-forward only a clean, non-diverged clone.
4. Re-run the candidate audit, risk scan, validator, and trigger tests before accepting the update.
5. For normalized copies, review and port upstream changes deliberately; do not overwrite the adaptation wholesale.

## Rollback or Remove

- For a symlink, verify `readlink` points to the expected source, then unlink only that exact link.
- For a copied skill, move the exact directory to a dated quarantine or Trash location rather than deleting it immediately.
- For a plugin or runtime, use its native disable/uninstall flow and confirm hooks, services, MCP entries, credentials, and background processes are removed or intentionally retained.
- Restore the recorded previous commit or prior normalized copy, then rerun validation.

## Installation Receipt

Return and record:

```text
upstream_url:
source_subpath:
source_commit:
license:
classification:
destination:
install_method: native | symlink | normalized-copy | project-local
adaptations:
validation:
positive_trigger:
negative_trigger:
update_method:
rollback_method:
```
