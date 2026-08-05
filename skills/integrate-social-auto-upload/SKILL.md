---
name: integrate-social-auto-upload
description: Audit, install in an isolated environment, or prepare the `sau` CLI for dreammis/social-auto-upload across Douyin, Kuaishou, Xiaohongshu, and Bilibili. Use only when the user explicitly names social-auto-upload, SAU, or asks for its login, cookie-check, video-upload, note-upload, or scheduled-publishing CLI. Do not trigger for drafting content, generic platform help, or publishing through official browser/API tools.
---

# Integrate Social Auto Upload

Treat setup, login, account checks, and publishing as separate authorization gates. The pinned upstream has no LICENSE file.

## Workflow

1. Read [references/integration.md](references/integration.md) before installation or CLI use.
2. Confirm the user accepts evaluation-only use pending a valid upstream license. Do not redistribute or embed upstream code.
3. Resolve the repository and verify remote, pin, worktree, Python version, and destination.
4. For setup, preview dependency and browser downloads, then install only after approval.
5. For login or account checks, state platform, account alias, browser mode, credential artifacts, and whether external state changes. Obtain explicit approval.
6. For publishing, first produce a dry-run manifest containing platform, account, media, title, body, tags, thumbnail, product fields, schedule/timezone, and AIGC/copyright checks.
7. Display the final manifest and ask for single-use approval immediately before the command that can publish. Never infer approval from earlier setup or drafting.
8. Execute once. If the result is ambiguous, inspect status and stop; never retry publication automatically.
9. Redact Cookies, session data, verification codes, QR payloads, and account files from logs and output.

## Hard Stops

- Never write a verification code to `verify_code.txt` unless the user explicitly authorizes that exact local action; remove it only after confirming the tool created/used it as expected.
- Do not auto-download or auto-update `biliup` without showing the effect and obtaining approval.
- Do not use headless mode to bypass platform controls or perform unattended bulk posting.
- Prefer official platform interfaces or a user-controlled browser when the task does not specifically require SAU.

## Agent Output

Return the repository pin, license warning, setup status, dry-run/final manifest, approval boundary, one command result, and rollback steps.

