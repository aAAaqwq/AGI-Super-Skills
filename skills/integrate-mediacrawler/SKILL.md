---
name: integrate-mediacrawler
description: Audit, install for isolated non-commercial research, configure, or invoke the pinned NanmiCoder/MediaCrawler CLI with explicit platform, login, crawl scope, storage, and rate limits. Use only when the user explicitly names MediaCrawler or asks to connect that repository for authorized learning/research. Do not trigger for ordinary web research, social analytics, commercial monitoring, proxy rotation, or general scraping.
---

# Integrate MediaCrawler

Default to a dry-run integration plan. The upstream license permits learning/research, not commercial use.

## Workflow

1. Read [references/integration.md](references/integration.md) before any installation or command proposal.
2. Confirm the purpose is non-commercial research and the targets/data are owned, public with permitted collection, or explicitly authorized. Otherwise stop.
3. Resolve the repository and verify remote, pinned commit, license, and worktree.
4. Produce a bounded run manifest: platform, login mode, crawl type, exact IDs/keywords, maximum items, comments off/on, concurrency, output path, retention, and deletion plan.
5. Default to no proxy, no browser-profile reuse, no comments, concurrency 1, minimum item count, and a new isolated output directory.
6. Show installation and run commands before execution. Treat QR/phone/Cookie login as a separate sensitive action.
7. Never print or persist Cookie values in chat, logs, plans, or receipts.
8. Execute only after the user approves the bounded manifest and any login/browser access.
9. Verify output count and destination, then stop; do not expand scope automatically.

## Hard Stops

- Refuse commercial use, large-scale collection, private data, platform-control evasion, signature reverse engineering, CAPTCHA bypass, rotating proxies, or scraping that violates terms/robots/law.
- Do not connect to an existing Chrome profile unless the user explicitly authorizes that exact profile and read scope.
- Do not describe structural setup as runtime validation.

## Agent Output

Return the authorization basis, repository pin, dry-run manifest, commands, records created, secrets handling, and compliance limits.

