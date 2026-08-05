---
name: integrate-opencut
description: Set up, inspect, develop, build, or test the OpenCut rewrite repository with its pinned Proto, Moon, Bun, Rust, web, API, and desktop toolchain. Use when the user explicitly mentions OpenCut-app/OpenCut, the OpenCut rewrite, Moon tasks, its future Editor API/MCP/headless roadmap, or integrating the rewrite into an agent workflow. Do not use for the archived opencut-classic repository.
---

# Integrate OpenCut

Operate the rewrite as a source repository, not as a finished headless editor or released Agent API.

## Workflow

1. Read [references/integration.md](references/integration.md) before cloning, installing tools, running a task, or updating the pin.
2. Resolve an explicit repository path. Never overwrite an existing directory.
3. Verify remote, commit, license, and worktree status before mutation.
4. Classify the request as inspect, install, web, API, desktop, build/test, or deploy.
5. For inspection, use read-only Git and manifest commands only.
6. For installation, show destination and tool downloads before executing. Never run a remote script through a shell pipe.
7. Prefer the pinned `proto` and Moon tasks. Do not invent an `npm` root workflow.
8. Keep deploy, R2 upload, Wrangler remote operations, credentials, and paid services behind a separate explicit approval.
9. Verify the requested local task and report the exact commit and command used.

## Capability Boundary

- Treat Editor API, plugins, MCP, headless mode, and scripting as roadmap items until the checked-out commit contains a documented runnable interface.
- Keep `.env*`, Cloudflare credentials, and media private.
- Preserve dirty worktrees; do not update or switch commits without approval.
- Use `integrate-opencut-classic` for the archived implementation.

## Agent Output

Return the resolved path, remote, commit, selected task, commands proposed/executed, result, external-state changes, and remaining limitations.

