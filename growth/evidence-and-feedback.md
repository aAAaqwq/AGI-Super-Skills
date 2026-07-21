# Evidence and feedback ledger

Use this file as a template. Do not commit private user data or security details.

## Claim ledger

| ID | Proposed claim | Evidence and revision | Scope/limits | Reviewer | Status |
|---|---|---|---|---|---|
| C-001 | Installer previews before writing and requires `--apply` | `install.sh` at `[commit]`; isolated command transcript | Generic installer only | `[name]` | Draft |
| C-002 | Codex package is separate from starter kits | `.agents/plugins/marketplace.json`, `.codex/INDEX.md` at `[commit]` | Repository packaging, not every client version | `[name]` | Draft |

Allowed statuses: `Draft`, `Verified`, `Rejected`, `Expired`. Re-verify after relevant code, configuration, manifest, or test changes.

Catalog counts may be marked `Verified` only when `npm run validate` is green for the cited revision. Financial results, production readiness, security guarantees, and live validation require independent evidence beyond repository tests; omit them unless that evidence is reviewable and appropriately qualified.

## Feedback log

| Date | Channel | Sanitized signal | Related artifact | Action | Owner | G6 decision |
|---|---|---|---|---|---|---|
| YYYY-MM-DD | `[channel]` | `[question/correction without identity]` | `[link/revision]` | `[fix/test/decline]` | `[owner]` | Continue/revise/stop |

## Experiment record

- Campaign ID:
- Human owner and reviewer:
- Audience/problem hypothesis:
- Artifact revision and MVTA:
- Gates completed:
- Manual post URL, if approved:
- Observation window and denominators:
- Primary outcomes and guardrails:
- Corrections or removals:
- Decision and rationale:

Security reports belong in private GitHub Security Advisories, never in this ledger.
