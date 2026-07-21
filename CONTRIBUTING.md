# Contributing to AGI Super Team

Contributions should be reviewable, attributable, safe to test, and honest about support. Do not include secrets, private data, unlicensed content, or claims that cannot be reproduced.

## Before opening a pull request

1. Branch from `main` and keep the change focused.
2. Search for an existing skill, agent, or issue before adding a duplicate.
3. Record provenance for adapted material: upstream URL, revision or retrieval date, license, and what changed.
4. Add or update tests for executable behavior. For documentation, run examples in an isolated temporary destination when safe.
5. Run the repository checks:

   ```bash
   npm test
   npm run validate
   ```

6. Review the diff for credentials, personal data, unsafe shell commands, generated artifacts, and unsupported claims.

## Skills

A skill lives at `skills/<name>/SKILL.md`. Keep one clear purpose, document triggers and boundaries, and place optional scripts or assets in the same skill directory.

Commands must state prerequisites, expected effects, and recovery. Destructive, external, production, or account-changing operations need explicit human confirmation. Never embed credentials or encourage users to pipe unreviewed remote code into a shell.

## Agents

An agent lives at `agents/<id>/` and normally includes `SOUL.md` and `AGENTS.md`; other persona or workflow files are optional. Keep role boundaries clear and use mentor references only as creative framing, not affiliation or endorsement.

## Provenance and licensing

For copied or adapted content, include the source project, immutable revision where possible, source license, and adaptation summary in the relevant provenance file or pull-request description.

Confirm that the source license permits redistribution. Do not submit scraped private content, proprietary prompts, model outputs with unclear rights, or generated code copied from an unverified source.

## Testing evidence

The pull request must include:

- exact commands executed and their results;
- the harness and relevant version used for manual checks;
- fixtures or sanitized inputs needed to reproduce the result;
- limitations, skipped checks, and untested environments;
- screenshots only when they add evidence and contain no sensitive data.

Do not claim “production-ready,” “live-validated,” profitable, secure, or universally compatible solely from unit tests or a local demo.

## Pull request scope

Use `.github/PULL_REQUEST_TEMPLATE.md`. Describe behavior before and after, risk, rollback, provenance, and evidence. Maintainers may ask for a smaller change or reject additions that cannot be safely maintained.

Report vulnerabilities privately as described in [SECURITY.md](./SECURITY.md). Follow [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) in all project spaces.
