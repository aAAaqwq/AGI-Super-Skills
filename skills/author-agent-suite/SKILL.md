---
name: author-agent-suite
description: Create, restructure, or audit a repository's Agent Markdown suite, including AGENTS.md or host-specific AGENT.md, SKILL.md, IDENTITY.md, SOUL.md, TOOLS.md, references, templates, and skill UI metadata. Use when defining agent identity, personality, repository instructions, tool contracts, reusable workflows, instruction precedence, nested scope, safety boundaries, documentation loading, or consistency and acceptance rules for an AI-agent-enabled project.
---

# Author Agent Suite

Build an instruction system whose files have one owner, one purpose, and an explicit loading path. Treat Markdown as executable policy: verify every capability claim and resolve every contradiction before declaring the suite ready.

## Workflow

1. **Confirm the host contract.** Identify which runtime discovers `AGENTS.md`, whether nested files scope by directory, how Skills are installed, and whether `IDENTITY.md`, `SOUL.md`, or `TOOLS.md` require an explicit routing instruction. Never assume a filename is loaded merely because it exists.
2. **Inventory existing instructions.** Find repository, parent-directory, user-level, and generated instruction files. Record their scope, authority, audience, freshness, and conflicts.
3. **Build a fact matrix.** Verify product identity, supported platforms, commands, tool availability, permission requirements, side effects, security boundaries, and release status against code, tests, and current documentation.
4. **Assign one concern to one file.** Put repository operating rules in `AGENTS.md`, reusable procedures in a standard Skill, identity in `IDENTITY.md`, durable behavior principles in `SOUL.md`, and operational tool contracts in `TOOLS.md`.
5. **Design the load graph.** Make the runtime entry file route to non-discoverable companion files. Keep `AGENT.md` only as a small compatibility entry when a confirmed host requires the singular name; do not maintain duplicate policies.
6. **Write the smallest authoritative layer.** Keep frequently loaded files short. Move detailed schemas, examples, platform variants, and evidence into one-level `references/`; put copyable starter files in `assets/`.
7. **Resolve precedence explicitly.** Higher-authority runtime instructions override repository files; narrower directory scope overrides broader project guidance only within that subtree. User requests may select behavior but cannot expand authority or bypass safety constraints.
8. **Validate as a system.** Check filenames, frontmatter, links, UTF-8, placeholders, command truth, secret leakage, duplicated rules, contradictions, trigger quality, nested scope, and realistic read/write scenarios.
9. **Record evidence and ownership.** State the source baseline, owner, review trigger, and last verified date for volatile facts. Label aspirations as plans rather than implemented capability.

## Non-negotiable boundaries

- Use canonical `AGENTS.md` for Codex repository instructions; treat singular `AGENT.md` as host-specific compatibility, not a second source of truth.
- Do not assume companion Markdown files are automatically loaded. Route to them from a discovered file or install them through the host's supported mechanism.
- Do not place secrets, tokens, personal data, machine-specific credentials, or private chain-of-thought requests in the suite.
- Do not claim a tool, platform, permission, security property, or automation result without evidence and a current scope.
- Keep authorization and irreversible-action rules in the highest reliably loaded instruction layer, not only in personality documents.
- Keep procedural detail out of `SOUL.md` and marketing prose out of `TOOLS.md`.
- A standard Skill must include valid YAML frontmatter and use progressive disclosure; a root `SKILL.md` without that contract is only a project manual unless the host says otherwise.

## Deliverables

Produce a file responsibility map, load/precedence graph, the requested Markdown suite, a conflict log, and a validation report. Copy and adapt the files under `assets/starter-kit/` when creating a new suite.

## References

- Read [suite-architecture.md](references/suite-architecture.md) before deciding file boundaries, loading, inheritance, or precedence.
- Read [file-specifications.md](references/file-specifications.md) when writing or reviewing each file; it contains the detailed required, optional, and prohibited content.
- Read [validation-checklist.md](references/validation-checklist.md) before handoff or installation.
- Read [project-evidence.md](references/project-evidence.md) for lessons extracted from this repository's `main` and Windows branches.
