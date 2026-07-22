---
name: agent-skill-repository-index
description: "Find and compare Daniel's reviewed GitHub skill sources. Use for high-star skill discovery, link checks, or safe installation, update, and removal of one selected skill."
---

# Daniel's Recommended High-Star GitHub Skills

Route agents to reviewed upstream repositories without globally activating every repository. Treat popularity as a discovery signal, never as proof of quality or safety.

## Load Only What You Need

- Read [references/repositories.md](references/repositories.md) to find and compare sources.
- Read [references/star-snapshot.md](references/star-snapshot.md) only when the user asks about popularity or ranking.
- Read [references/installing.md](references/installing.md) before installing, updating, linking, migrating, or removing a skill.
- Run `python3 scripts/verify_repository_index.py --repo-root /absolute/path/to/repos` to verify index-to-clone identity. Add `--remote` when current GitHub reachability matters.

## Fast Workflow

1. Resolve intent: discovery, comparison, installation, update, removal, or link verification.
2. Search already installed skills first. Reuse an equivalent Codex-native skill instead of adding a duplicate.
3. Shortlist at most three sources by capability, runtime compatibility, maintenance, license, and risk class. Use stars only as a tie-breaker.
4. If a repository is an `awesome-*` catalog or has no root `SKILL.md`, use it for discovery only. Trace the selected item to its original upstream.
5. Inspect one candidate directory completely: `SKILL.md`, adjacent resources, license, Git remote, commit, worktree state, scripts, hooks, dependencies, credentials, network actions, and persistent state.
6. Classify it as `DAILY`, `LIBRARY`, `QUARANTINE`, or `DUPLICATE`. Do not install `QUARANTINE` capabilities without explicit authorization for their runtime effects.
7. Follow [references/installing.md](references/installing.md). Install only the reviewed skill subdirectory, not the entire aggregator.
8. Validate metadata and resources, then test one positive trigger and one negative trigger.
9. Return an installation receipt containing upstream URL, local source, subpath, commit, license, class, target, install method, adaptations, checks, update method, and rollback method.

## Efficient Search

Search metadata before opening files:

```bash
rg -n --glob 'SKILL.md' '^(name|description):.*KEYWORD' /absolute/path/to/repos
```

Then inspect only the chosen skill directory. Scan risky behavior without printing secret values:

```bash
rg -l --hidden '(curl.+\|\s*(sh|bash)|sudo\b|rm\s+-rf|cookies?|auth|token|secret|hook|auto.?update|deploy|tunnel|daemon|memory)' /absolute/path/to/candidate
```

## Decision Rules

- Prefer the original upstream, a Codex-native plugin, or a single passive instruction skill.
- Prefer a symlink for a clean reviewed local source that should update with its repository; prefer a normalized copy when Codex-specific adaptation is required.
- Keep catalogs, full runtimes, hooks, MCP servers, auto-updaters, deployers, tunnels, browser profiles, and persistent-memory systems inactive during discovery.
- Preserve dirty repositories and existing targets. Never overwrite or delete them to complete an installation.
- Fetch live star counts only when the user asks for a current ranking. Label the bundled figures as Daniel's July 2026 snapshot.

For “redesign this landing page,” invoke the selected design skill. For “which high-star design skill repository does Daniel recommend, and install the safest option,” invoke this skill first.
