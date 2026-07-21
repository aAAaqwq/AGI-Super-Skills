# Security policy

## Report a vulnerability privately

Use [GitHub Security Advisories](https://github.com/aAAaqwq/AGI-Super-Team/security/advisories/new) to submit a private report. Do not open a public issue, discussion, or pull request for an undisclosed vulnerability.

Include the affected path and revision, impact, reproduction steps, prerequisites, and a suggested mitigation if available. Remove credentials, personal data, and production identifiers from evidence.

If private reporting is unavailable, do not publish exploit details. State only that the private channel is unavailable in a general repository discussion and wait for a maintainer-provided channel.

## Scope

Reports may cover repository-owned installers, scripts, plugin manifests, bundled skills, agent instructions, or documentation that creates a concrete security risk.

Third-party services, harnesses, models, and upstream dependencies are outside this project's control. Report their vulnerabilities to the relevant vendor, while privately notifying this project if its integration also needs mitigation.

## Response expectations

Maintainers will aim to acknowledge a report, assess severity, coordinate a fix, and publish remediation guidance. Response times are not guaranteed. Please allow reasonable time for remediation before disclosure.

## User safety

- Inspect a pinned checkout before running scripts; use the installer's preview before `--apply`.
- Keep API keys, tokens, private keys, browser sessions, and production configuration outside the repository.
- Use least-privilege credentials and isolated test accounts.
- Treat skills and agent output as untrusted instructions until reviewed.
- Require human approval for external messages, publishing, transactions, deployments, and destructive actions.
- Rotate and revoke an exposed credential immediately; deleting it from the latest revision is not sufficient because Git history may retain it.

No automated scan proves the absence of secrets or vulnerabilities. Contributors must combine repository checks, diff review, provenance review, and appropriate domain testing.
