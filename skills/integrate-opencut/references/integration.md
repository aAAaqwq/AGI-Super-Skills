# OpenCut rewrite integration reference

## Provenance

- Upstream: `https://github.com/OpenCut-app/OpenCut.git`
- Reviewed revision: `4d8c49ed0706c4dc145361e01c6b1f1a87cbb863`
- Default branch at review: `main`
- License: MIT; retain `LICENSE` and attribution.
- Adaptation: original code is not bundled. This Skill adds setup routing, Agent CLI guidance, and approval gates.

## Preflight

```bash
git -C <repo> remote get-url origin
git -C <repo> rev-parse HEAD
git -C <repo> status --short
test -f <repo>/LICENSE
```

Clone only into an absent destination:

```bash
git clone https://github.com/OpenCut-app/OpenCut.git <repo>
git -C <repo> checkout 4d8c49ed0706c4dc145361e01c6b1f1a87cbb863
```

Do not update a dirty clone. Do not claim a detached pin follows upstream automatically.

## Installation

The reviewed revision pins Moon `2.3.3`, Bun `1.3.11`, and Rust `1.97.0` in `.prototools`.

1. Check `proto --version`. If absent, direct the user to Moonrepo Proto's official installer/package instructions and let them inspect the installer. Never pipe a remote download directly into a shell or PowerShell evaluator.
2. Preview the tool versions and downloads.
3. When approved, run from the repository root:

```bash
proto use
```

## Agent CLI map

| Intent | Command | Effect |
| --- | --- | --- |
| List projects/tasks | `moon query projects` / `moon query tasks` | Read-only discovery |
| Web development | `moon run web:dev` | Local server, normally port 5173 |
| API development | `moon run api:dev` | Local Wrangler development server |
| Desktop development | `moon run desktop:dev` | Local Rust/desktop process; read `apps/desktop/README.md` first |
| Web build | `moon run web:build` | Local build artifacts |
| Web test | `moon run web:test` | Local Vitest suite |
| API build | `moon run api:build` | Wrangler dry-run build |

Confirm actual task names with `moon query tasks`; the project is under active redesign.

Never run `web:deploy`, `api:deploy`, `upload-logos`, Wrangler `--remote`, or credentialed Cloudflare commands without a separate explicit approval.

## Trigger checks

- Positive: “在 OpenCut 重写版固定提交上启动 web 开发环境。”
- Positive: “检查 OpenCut-app/OpenCut 当前有没有可用的 headless/MCP 接口。”
- Negative: “启动 opencut-classic。” Route to `integrate-opencut-classic`.
- Negative: “帮我剪一个视频。” Use an actual video-editing workflow, not this repository adapter.

## Rollback

Stop local processes, remove only the explicitly created local build/cache artifacts according to Moon/Proto documentation, and keep source changes. Removing a clone or toolchain requires a separate explicit request.
