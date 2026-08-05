# XHS-Downloader integration reference

## Provenance and license gate

- Upstream: `https://github.com/JoeanAmier/XHS-Downloader.git`
- Reviewed revision: `cdc02d0da867473d0d020adf8d26a939794a1a51`
- Declared package license and root file: GPL-3.0.
- Additional README language restricts commercial promotion, marketing, and relicensing without written authorization. Treat distribution/commercial use as unresolved pending legal review.
- Runtime: Python `>=3.12`.
- Adaptation: no upstream source is copied; this Skill adds authorization, loopback, privacy, and bounded-execution controls.

## Preflight and installation

Record the owner/permission for each target URL before setup. Verify remote, commit, worktree, license, Python, `uv`, destination, expected download folder, and free disk space.

After dependency approval:

```bash
cd <repo>
uv sync --no-dev
uv run main.py --help
```

Do not default to prebuilt release binaries, Docker images, browser userscripts, or removal of macOS quarantine attributes; each has a separate provenance/security effect.

## Agent CLI and modes

| Mode | Command | Notes |
| --- | --- | --- |
| TUI | `uv run main.py` | Interactive; writes settings/download records |
| CLI discovery | `uv run main.py --help` | Inspect current Click options before constructing a command |
| API loopback | See loopback command below | Long-running local service |
| MCP loopback | See loopback command below | Long-running local MCP service |

The reviewed `main.py` hardcodes server defaults to `0.0.0.0:5556`. Start loopback explicitly instead:

```bash
uv run python -c "from asyncio import run; from main import api_server; run(api_server(host='127.0.0.1', port=5556))"
```

```bash
uv run python -c "from asyncio import run; from main import mcp_server; run(mcp_server(host='127.0.0.1', port=5556))"
```

Confirm port availability first. Do not background the process unless the user requested a persistent service and a stop command is recorded.

For one CLI download, inspect `uv run main.py --help` on the pinned checkout and construct the narrowest command with one authorized URL and a new output directory. Do not guess options across versions.

## Data and credentials

- Default persistent state includes `Volume/settings.json`, download data, and SQLite records.
- Keep Cookie unset unless needed. If needed, accept it only through a user-controlled local secret path; never echo it, place it in shell history, or commit it.
- Disable clipboard watching, userscript server, automated scrolling, proxy, and bulk modes unless separately reviewed and authorized.

## Trigger checks

- Positive: “用 XHS-Downloader 下载我自己发布的这一条笔记，先列出会写哪些文件。”
- Positive: “在 127.0.0.1 启动 XHS-Downloader MCP 做隔离测试。”
- Negative: “批量下载竞品账号全部作品。” Refuse absent explicit rights and bounded scope.
- Negative: “分析小红书选题。” Use a research/content Skill.

## Rollback

Stop loopback services. Report settings, databases, downloaded files, volumes, and virtual environment. Delete none of them without an explicit request and exact target confirmation.

