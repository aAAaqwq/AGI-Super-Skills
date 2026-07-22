# 🚀 Role-pack bootstrap

Use this portable startup order inside an installed workspace:

1. Read `../agents/CHARTER.md` for human authority, safety, and evidence boundaries.
2. Read `../agents/COLLABORATION.md` for routing, delegation, and handoff contracts.
3. Read `SOUL.md`, `AGENTS.md`, `IDENTITY.md`, `USER.md`, `TOOLS.md`, and `WORKFLOW.md` when present.
4. Inspect the local `skills/` directory before invoking any skill or external tool.
5. State the objective, planned artifacts, checks, limits, and actions requiring human approval.

Repository structure checks do not prove runtime behavior. If a required file, skill, credential, or receipt is missing, report the gap instead of inventing it.

Do not assume a host-specific home directory. Write new session memory only inside the installed workspace, and never overwrite existing user or persona files.
