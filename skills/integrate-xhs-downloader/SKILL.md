---
name: integrate-xhs-downloader
description: Audit, install, configure, or invoke the pinned JoeanAmier/XHS-Downloader repository for authorized Xiaohongshu/RedNote link extraction, owned-media download, local API, or local MCP evaluation. Use only when the user explicitly names XHS-Downloader or supplies Xiaohongshu content they own or have permission to download. Do not trigger for generic Xiaohongshu research, competitor scraping, or unauthorized media acquisition.
---

# Integrate XHS Downloader

Use only for content the user owns or is explicitly allowed to download. Treat the GPL-3.0 file and additional README restrictions as a license-clarification requirement for distribution or commercial use.

## Workflow

1. Read [references/integration.md](references/integration.md) before installation, download, API, MCP, Docker, or Cookie use.
2. Record the authorization basis for every target URL and the allowed output purpose.
3. Resolve and verify remote, pinned commit, license files, README restrictions, and worktree.
4. Choose one mode: static inspection, local TUI/CLI, one authorized download, loopback API, loopback MCP, or Docker evaluation.
5. Preview dependency, server, port, volume, download, and persistent database effects.
6. Default services to `127.0.0.1`; never expose `0.0.0.0` without explicit network-scope approval and access controls.
7. Keep Cookie optional. Never collect it automatically or print it; prefer unauthenticated access when sufficient.
8. Run one bounded request/download, verify destination and count, then stop.

## Hard Stops

- Refuse copyrighted media without permission, bulk account/keyword collection, automated scrolling, private data, or risk-control evasion.
- Do not enable clipboard monitoring, background servers, browser userscripts, proxies, or persistent containers implicitly.
- Do not redistribute builds or derivative packages until the GPL/additional-term conflict is reviewed.

## Agent Output

Return authorization, repository pin, mode, exact input count, commands, bound address/port, artifacts, persistent state, and license limitations.

