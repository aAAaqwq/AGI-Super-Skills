---
name: integrate-opencut-classic
description: Set up, inspect, run, build, or test the archived OpenCut Classic repository and its Bun, Next.js web, Docker services, and optional Rust/WASM paths. Use when the user explicitly mentions OpenCut Classic, opencut-classic, the legacy OpenCut web editor, or evaluating its import, timeline, preview, or export implementation. Do not use for the current OpenCut rewrite.
---

# Integrate OpenCut Classic

Operate the legacy repository as archived, unmaintained evaluation software.

## Workflow

1. Read [references/integration.md](references/integration.md) before cloning, installing, starting services, or changing configuration.
2. Verify remote, pinned commit, MIT license, and clean/dirty status.
3. Choose the narrowest route: static inspection, frontend-only dev, full local services, build/test, or optional WASM/desktop work.
4. Show all dependency, environment-file, Docker, port, and filesystem effects before installation.
5. Prefer frontend-only setup when database and Redis are unnecessary.
6. Keep Docker, database writes, container lifecycle, deploy scripts, package publication, and external services behind explicit approval.
7. Run a focused validation for the selected route and report archived status and known failures without upgrading claims.

## Capability Boundary

- Never call this maintained or production-ready.
- Do not claim import, timeline, preview, or export works until reproduced on the pinned checkout with owned test media.
- Do not place secrets in `.env.local`; start from the example and review every value.
- Preserve dirty worktrees and existing containers.

## Agent Output

Return repository identity, chosen route, prerequisites, commands, ports/containers changed, validation evidence, and unresolved legacy risks.

