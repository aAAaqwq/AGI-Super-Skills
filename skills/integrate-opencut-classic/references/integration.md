# OpenCut Classic integration reference

## Provenance

- Upstream: `https://github.com/OpenCut-app/opencut-classic.git`
- Reviewed revision: `cf5e79e919144200294fb9fed22a222592a0aeea`
- Default branch at review: `main`
- License: MIT; retain `LICENSE` and attribution.
- Status: archived and no longer maintained.
- Adaptation: original code is not bundled. This Skill adds narrow setup routes and honest evidence boundaries.

## Preflight and clone

```bash
git -C <repo> remote get-url origin
git -C <repo> rev-parse HEAD
git -C <repo> status --short
```

```bash
git clone https://github.com/OpenCut-app/opencut-classic.git <repo>
git -C <repo> checkout cf5e79e919144200294fb9fed22a222592a0aeea
```

Require Bun `1.2.18` for the reviewed root manifest. Docker is optional.

## Installation routes

Frontend-only route:

```bash
cd <repo>
test ! -e apps/web/.env.local
cp apps/web/.env.example apps/web/.env.local
bun install
bun dev:web
```

Review `.env.local` before starting and never add secrets from chat. Use frontend-only mode when database/Redis are not required.

Full local services, only after approval:

```bash
docker compose up -d db redis serverless-redis-http
bun dev:web
```

Record container names, ports, volumes, and the exact rollback command before starting.

## Agent CLI map

| Intent | Command | Effect |
| --- | --- | --- |
| Web dev | `bun dev:web` | Starts legacy Next.js web app |
| Web build | `bun run build:web` | Builds web workspace |
| Web lint | `bun run lint:web` | ESLint on web source |
| Tests | `bun test` | Bun test suite |
| WASM build | `bun run build:wasm` | Requires Rust and wasm-pack; creates package output |
| Web preview | `bun run preview:web` | Local preview process |

Do not run `deploy:web`, `publish:wasm`, `docker compose up -d` for the full stack, or modify existing containers without separate approval.

## Verification ladder

1. Dependency install exits successfully.
2. Focused lint/test/build exits successfully.
3. Web UI loads locally.
4. Import/timeline/preview/export is manually reproduced with owned test media.

Do not skip from step 1 or 2 to a claim that the editor workflow works.

## Trigger checks

- Positive: “在 opencut-classic 固定版本里检查时间线和导出实现。”
- Positive: “本地启动旧版 OpenCut 前端，不要启动数据库。”
- Negative: “查看 OpenCut 重写版的 MCP 路线图。” Route to `integrate-opencut`.

## Rollback

Stop only processes or containers started in this run. Preserve volumes unless the user explicitly requests deletion. Restore `.env.local` only if this run created it and the user approves removal.
