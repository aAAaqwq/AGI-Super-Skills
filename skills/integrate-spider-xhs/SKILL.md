---
name: integrate-spider-xhs
description: Perform static architecture, dependency, license, and interface assessment of the pinned cv-cat/Spider_XHS repository and design a compliant replacement or integration boundary. Use only when the user explicitly names Spider_XHS, its PC/Creator/KOL/Qianfan APIs, or asks to audit that repository. Do not use to run its login, signing, scraping, proxy, fingerprint, anti-detection, invitation, upload, or publishing capabilities.
---

# Integrate Spider XHS

Keep this adapter audit-only. The pinned repository has no LICENSE file, claims non-commercial-only use, and includes reverse-engineered signing and risk-control behavior.

## Workflow

1. Read [references/integration.md](references/integration.md) before inspecting or proposing any connection.
2. Resolve the local repository and verify remote, pinned commit, missing LICENSE, README restrictions, and worktree.
3. Inspect manifests and interfaces statically. Do not install dependencies or execute repository code.
4. Inventory the requested capability and classify it as read-only public data, account/private data, login, signing, anti-detection, creator publishing, KOL data, distributor data, or local utility.
5. Stop unsupported categories and propose an official API, user-controlled browser, exported first-party data, or licensed vendor alternative.
6. If the user obtains written permission and platform authorization, require a fresh security/legal review before changing this audit-only boundary.
7. Report facts from the pinned source without reproducing signing algorithms, secrets, or bypass instructions.

## Hard Stops

- Never execute `pip install`, `npm install`, Docker, `python main.py`, or `python -m spider.spider` for this repository under this Skill.
- Never assist with signature reverse engineering, fingerprint mutation, proxy rotation, automatic retry intended to evade controls, CAPTCHA/SMS bypass, scraping private data, or unauthorized publishing.
- Never treat a README badge as a license grant.

## Agent Output

Return repository identity, license state, static interface map, blocked capabilities, compliant alternatives, and requirements for any future re-review.

