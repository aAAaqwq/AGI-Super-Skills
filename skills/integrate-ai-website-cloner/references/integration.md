# AI website cloner template integration reference

## Provenance

- Upstream: `https://github.com/JCodesMore/ai-website-cloner-template.git`
- Reviewed revision: `58e00d5369181dc0b84b45a2a55e6f64a017f59b`
- License: MIT; preserve `LICENSE` and attribution.
- Reviewed runtime: Node `>=24`, Next.js `16.2.1`, React `19.2.4`.
- Adaptation: this Skill does not bundle the template. It adds project creation, authorization, Codex metadata normalization, and validation guidance.

## Choose a creation route

### GitHub template route

Prefer GitHub “Use this template.” Creating a repository changes external state. Before using `gh`, show owner, name, visibility, template, and clone destination, then obtain approval.

```bash
gh repo create <owner>/<new-repo> \
  --template JCodesMore/ai-website-cloner-template \
  --private \
  --clone
```

The live template may differ from the reviewed revision. Record the resulting source date/commit and re-audit changes before using the bundled Skill.

### Exact reviewed local snapshot

For an offline, exact-revision evaluation, clone the upstream into an absent source directory, checkout the reviewed commit, and export it to a separate absent project directory using `git archive`. Preserve `LICENSE`. Do not work directly in the upstream clone.

## Install and baseline

From the derived project, after reviewing the lockfile and approving dependency installation:

```bash
npm install
npm run check
```

Standard Agent CLI:

| Intent | Command |
| --- | --- |
| Dev server | `npm run dev` |
| Lint | `npm run lint` |
| Type check | `npm run typecheck` |
| Build | `npm run build` |
| Full local gate | `npm run check` |

## Normalize the project-local Skill

The reviewed `.codex/skills/clone-website/SKILL.md` frontmatter includes `argument-hint` and `user-invocable`, which the Codex Skill validator rejects. In the derived project only:

1. Keep only `name` and a permission-aware `description` in frontmatter.
2. Add an explicit ownership/authorization gate before browser access or asset extraction.
3. Keep the Skill project-local; do not link it globally.
4. Preserve upstream provenance and note the adaptation.
5. Validate with Codex `quick_validate.py` when available.

Do not copy the full upstream Skill into AGI-Super-Team: it is large, template-specific, and overlaps native `url-to-code` behavior.

## Target authorization manifest

Record before browsing:

```text
target_url:
owner_or_permission:
permitted_pages:
permitted_text_assets_fonts:
terms_or_robots_constraints:
authentication_required: no
retention_and_deletion:
deployment_allowed: no
```

If ownership/permission is missing, stop. Accessibility, privacy, and security remain required even though the upstream workflow lists accessibility as out of scope.

## Trigger checks

- Positive: “把 ai-website-cloner-template 的项目内 Skill 适配成 Codex 可校验版本。”
- Positive: “从 JCodesMore 模板新建一个私有仓库，我有目标站授权。”
- Negative: “照着这个 URL 做一个页面。” Use native authorized URL-to-code/product-design routing.
- Negative: “复制登录后才能看的竞品后台。” Refuse.

## Rollback

Stop local servers. Revert only adapter edits made in the derived project. Repository deletion, GitHub deletion, dependency removal, or downloaded-asset deletion requires explicit target confirmation.

