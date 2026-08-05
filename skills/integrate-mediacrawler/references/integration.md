# MediaCrawler integration reference

## Provenance and permission

- Upstream: `https://github.com/NanmiCoder/MediaCrawler.git`
- Reviewed revision: `17f66121e0fcc40fc23958b995bec873d422667d`
- License: `NON-COMMERCIAL LEARNING LICENSE 1.1`.
- Adaptation: no upstream code is copied. This Skill limits the repository to authorized, non-commercial learning/research.

Before setup, record: purpose, authorization basis, target platform, exact records, maximum count, storage/retention, and confirmation that the work is non-commercial.

## Preflight and installation

```bash
git -C <repo> remote get-url origin
git -C <repo> rev-parse HEAD
git -C <repo> status --short
python3 --version
uv --version
```

Clone to an absent isolated directory and checkout the reviewed revision. Python must be at least 3.11.

After the user approves dependency installation:

```bash
cd <repo>
uv sync
```

Default CDP mode connects to an existing Chrome instance and login state. Do not enable it implicitly. Standard Playwright mode may require `uv run playwright install`, which downloads browser binaries and needs a separate preview/approval.

## Agent CLI

Discover the pinned interface first:

```bash
uv run main.py --help
```

Bounded template:

```bash
uv run main.py \
  --platform <xhs|dy|ks|bili|wb|tieba|zhihu> \
  --lt <qrcode|phone|cookie> \
  --type <search|detail|creator> \
  --crawler_max_notes_count <small-positive-integer> \
  --max_concurrency_num 1 \
  --get_comment no \
  --get_sub_comment no \
  --enable_ip_proxy no \
  --save_data_option jsonl \
  --save_data_path <new-isolated-output>
```

Add exactly one scope selector only after review:

- Search: `--keywords <bounded-keywords>`
- Detail: `--specified_id <authorized-id-or-url>`
- Creator: `--creator_id <authorized-id-or-url>`

Never put a Cookie directly in a shell command because it leaks through history/process listings. Use a user-approved local secret mechanism supported by the repository, without printing the value.

## Web UI

The upstream documents separate API and Vite dev servers. Starting them creates long-running processes and opens ports; preview both commands and bind scope before execution. Do not expose the API publicly.

## Trigger checks

- Positive: “用 MediaCrawler 对我自己的 2 篇小红书笔记做非商业研究，先给 dry-run。”
- Positive: “审计 MediaCrawler 的 CLI 参数，不运行爬虫。”
- Negative: “做商业竞品全量采集并轮换代理。” Refuse.
- Negative: “研究今天的行业新闻。” Use a normal research Skill.

## Rollback and stop

Stop after the approved count. Report files/databases created. Remove outputs or virtual environments only on explicit request; otherwise provide exact paths and retention guidance.
