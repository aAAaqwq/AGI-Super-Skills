# social-auto-upload integration reference

## Contents

- [Provenance and license gate](#provenance-and-license-gate)
- [Install for isolated evaluation](#install-for-isolated-evaluation)
- [Agent CLI map](#agent-cli-map)
- [Approval sequence](#approval-sequence)
- [Trigger checks](#trigger-checks)
- [Rollback](#rollback)

## Provenance and license gate

- Upstream: `https://github.com/dreammis/social-auto-upload.git`
- Reviewed revision: `dde0eacb91268de2680825396eea873f8d8ddb38`
- License: no `LICENSE` or `COPYING` file at the reviewed revision. README statements are not a substitute for a license grant.
- Runtime: Python `>=3.10,<3.13`; CLI entry point `sau = sau_cli:main`.
- Adaptation: no upstream code is copied. This Skill adds evaluation-only setup and approval-gated CLI orchestration.

## Install for isolated evaluation

Verify remote, commit, worktree, Python, `uv`, and absent target. Then preview:

```bash
cd <repo>
test ! -e .venv
test ! -e conf.py
uv venv
uv pip install -e .
cp conf.example.py conf.py
```

Review `conf.py`; never copy secrets into it from chat. Patchright Chromium is a separate network download:

```bash
patchright install chromium
```

Do not silently route downloads through an unreviewed mirror. After installation, use read-only help:

```bash
sau --help
sau douyin --help
sau kuaishou --help
sau xiaohongshu --help
sau bilibili --help
```

## Agent CLI map

Replace `<platform>` with `douyin`, `kuaishou`, `xiaohongshu`, or `bilibili`.

| Intent | Command shape | External effect |
| --- | --- | --- |
| Help | `sau <platform> --help` | None expected |
| Login | `sau <platform> login --account <alias>` | Creates/refreshes account state; user interaction |
| Check | `sau <platform> check --account <alias>` | Reads account state and contacts platform |
| Video publish | `sau <platform> upload-video ...` | Publishes immediately unless scheduled |
| Note publish | `sau <platform> upload-note ...` | Publishes immediately unless scheduled; unavailable for Bilibili |

Video command template, execute only after final approval:

```bash
sau <platform> upload-video \
  --account <alias> \
  --file <absolute-owned-media-path> \
  --title <title> \
  --desc <description> \
  --tags <comma-separated-tags> \
  [--thumbnail <path>] \
  [--schedule "YYYY-MM-DD HH:MM"] \
  [--headed]
```

Note template for Douyin/Kuaishou/Xiaohongshu:

```bash
sau <platform> upload-note \
  --account <alias> \
  --images <absolute-image-paths...> \
  --title <title> \
  --note <body> \
  --tags <comma-separated-tags> \
  [--schedule "YYYY-MM-DD HH:MM"] \
  [--headed]
```

Bilibili video additionally requires `--tid <category-id>`. Its first command may download `biliup`, and later commands may update it; approve this supply-chain effect separately.

## Approval sequence

1. Setup approval.
2. Login/check approval for one named platform/account.
3. Content and media review.
4. Final publish manifest including timezone and AIGC/copyright status.
5. Single-use approval immediately before execution.
6. One attempt; ambiguous result means stop and inspect.

Never reveal QR payloads, Cookie/session files, verification codes, account paths, or tokens. Render a QR image to the user only when the client supports it and the user asked to log in.

## Trigger checks

- Positive: “显式用 social-auto-upload 的 `sau` 检查测试账号状态。”
- Positive: “安装 SAU 到隔离虚拟环境，但不要登录或发布。”
- Negative: “帮我写一篇抖音文案。” Use a content Skill.
- Negative: “用官方浏览器帮我发。” Use the authorized browser workflow.

## Rollback

Stop processes, report generated account/config/browser artifacts, and provide exact paths. Remove the virtual environment, browser download, account state, or repository only after an explicit removal request.
