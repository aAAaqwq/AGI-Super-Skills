# Contributing

## How to contribute
- Bugs and focused fixes: open a PR.
- New features or architecture changes: open an issue/discussion first.
- Questions: open an issue or discussion.

## Before you open a PR
- Search existing issues and PRs first.
- Keep PRs focused; do not mix unrelated concerns.
- Use the issue forms in `.github/ISSUE_TEMPLATE/` for new reports and requests.

## Branches and commits
- Branch names should be short and descriptive (example: `codex/<topic>`).
- Prefer commit format `type(scope): subject`.

## Validation expectations
Include exact commands and outcomes in every PR.

For script changes, run:

```bash
while IFS= read -r script; do [[ -f "$script" ]] || continue; bash -n "$script"; done < <(git ls-files scripts)
while IFS= read -r script; do [[ -f "$script" ]] || continue; shellcheck "$script"; done < <(git ls-files scripts)
./scripts/doc-drift-check
./scripts/smoke-wrappers.sh
```

When wrapper behavior is involved, also run:

```bash
./scripts/doctor
```

## AI-assisted contributions
AI-assisted PRs are welcome. Be explicit:
- Mark AI assistance in the PR.
- State testing level (untested/lightly tested/fully tested).
- Include prompt/session notes when feasible.
- Confirm you understand the final code and behavior.

## PR requirements
Complete all sections in `.github/pull_request_template.md`, especially:
- Security impact
- Repro + verification
- Human verification
- Compatibility/migration
- Failure recovery
