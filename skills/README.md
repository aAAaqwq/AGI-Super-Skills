# Skills library

This directory contains the repository's tracked physical skills. A valid inventory entry is a real directory with a `SKILL.md` entrypoint; symlinks are forbidden.

Do not use this README as an inventory database. The canonical rules and active requirements live in [`config/team-manifest.json`](../config/team-manifest.json) and are calculated by the repository model.

## Browse with intent

Start from the task rather than the raw directory size:

- [Starter kits](../starter-kits/) provide focused role and skill selections.
- [Agent tool maps](../agents/) show skills used by active roles.
- [Practical guides](../docs/guides/) cover installation, compatibility, and workflow boundaries.
- [Skill matrix](../docs/skills-matrix.md) provides a generated cross-reference.

Search names and descriptions locally:

```bash
find skills -mindepth 2 -maxdepth 2 -type f -name SKILL.md | sort
rg -n '^description:' skills -g SKILL.md
```

## Inventory contract

The validator counts only skills that are:

1. tracked by Git;
2. physical directories rather than symlinks;
3. present in the working tree; and
4. backed by a `SKILL.md` entrypoint.

Run the source-of-truth check for the current revision:

```bash
npm run validate -- --warnings-as-errors
```

Active Agent references must resolve. Missing third-party recommendations belong in the manifest's `recommendedExternal` list and are not represented as bundled skills.

## Removed links and provenance

The refactor removed machine-local skill links that could not work in another checkout. Their source hints and status remain recorded in [`config/external-skill-sources.json`](../config/external-skill-sources.json).

A removed entry should return only after its source, license, pinned revision, physical contents, and validation are clear.

## Contributing

New or restored skills must include understandable instructions, provenance, license compatibility, and no secrets or host-specific paths.

Before opening a pull request, run:

```bash
npm test
npm run validate -- --warnings-as-errors
git diff --check
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full review contract.
