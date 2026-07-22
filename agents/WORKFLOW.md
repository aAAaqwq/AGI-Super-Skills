# 🔁 Portable role workflow

This workflow is copied into every generic role workspace. A harness supplies models, tools, delegation, and scheduling; none of those capabilities are assumed to exist.

## 1. Brief

- Restate the requested outcome, audience, constraints, and non-goals.
- Identify external writes, credentials, money, publishing, deployment, or destructive actions that require human approval.
- Inspect only the local files and capabilities actually available.

## 2. Plan

- Choose the smallest relevant local skills.
- Split independent work only when the harness exposes a delegation capability.
- Name artifacts, owners, dependencies, acceptance checks, and rollback.
- If scheduling is requested, provide a schedule proposal; do not claim it is active until the harness confirms it.

## 3. Build

- Keep changes local and reversible.
- Preserve existing user, persona, and skill files.
- Record assumptions and source evidence beside the artifact.
- Stop before any unapproved external or irreversible action.

## 4. Review

- Run the relevant deterministic checks.
- Ask the domain owner or Governor role for independent review when available.
- Separate structural evidence from semantic quality and runtime outcomes.
- Report missing capabilities or evidence as `Validation pending`.

## 5. Release handoff

Provide artifact paths, changes, verification, limitations, approvals still required, and rollback. Never report a delegated task, schedule, publication, deployment, or transaction as complete without observable confirmation from the active harness or human operator.
