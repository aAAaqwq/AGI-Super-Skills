---
name: integrate-ai-website-cloner
description: Create or inspect a project derived from JCodesMore/ai-website-cloner-template, normalize its bundled clone-website workflow for Codex, and verify its Next.js scaffold. Use when the user explicitly names that repository/template or asks to install its bundled Agent Skill into a project they created from the template. Do not trigger for general website cloning, redesign, screenshot-to-code, or URL-to-code requests.
---

# Integrate AI Website Cloner

Use this Skill to prepare the template and its project-local workflow, not to globally replace a native URL-to-code Skill.

## Workflow

1. Read [references/integration.md](references/integration.md) before creating a repository, installing dependencies, or adapting the bundled Skill.
2. Confirm the user owns or has explicit permission to reproduce every target site, asset, text, font, and interaction; otherwise stop.
3. Prefer creating a new repository from the upstream GitHub template. Treat that as an external-state action and obtain approval before invoking GitHub.
4. Verify remote/template provenance, pinned source commit, MIT license, Node version, clean destination, and target-project ownership.
5. Install dependencies only inside the new project after showing the command and lockfile effects.
6. Keep the bundled `clone-website` Skill project-local. Normalize unsupported frontmatter only in the derived project and preserve provenance.
7. Before browsing a target, record authorization, terms/robots constraints, permitted pages, permitted assets, and data retention.
8. Run baseline `npm run check`, then use the project-local workflow. Do not download assets outside the approved scope.
9. Run `npm run check` and visual QA after implementation; report remaining differences and licensing exclusions.

## Capability Boundary

- Do not globally install this adapter as a generic “clone any website” trigger.
- Do not copy login-only pages, private data, trademarks for deceptive use, or assets without permission.
- Do not deploy or publish the derived site without a separate approval.
- Use native product-design URL/screenshot workflows for ordinary authorized recreation tasks not tied to this template.

## Agent Output

Return template provenance, derived repository/destination, authorization scope, adapted files, commands, checks, excluded assets, and deployment status.

