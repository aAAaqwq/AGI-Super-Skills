# Orchestration Scripts

Companion automation scripts for the orchestration workflow skill. Designed for **any agent on any machine** — no hardcoded project paths.

## Scripts

### `watchdog.sh` — Background Worker Monitor

Polls a git worktree for ACP Worker completion. Use with Mode 6 (async polling).

```bash
# Start in background
nohup ./scripts/watchdog.sh /tmp/flyme-feature 30 10 > /tmp/watchdog.log &

# Check result later
cat /tmp/watchdog.log | tail -1 | jq .
```

**Output** (JSON lines):
- `{"status":"completed","commit":"abc1234 feat: ..."}` — Worker committed
- `{"status":"exited_uncommitted","modified_files":3}` — Worker died, files salvageable
- `{"status":"idle_timeout","idle_seconds":600}` — Possible hang
- `{"status":"polling","poll":5,"acpx":2,"modified":3}` — Still working

**Customizable**:
- `poll_interval` (default 30s) — how often to check
- `max_idle_min` (default 10) — how long no-change before flagging

### `deploy-verify.sh` — Deploy + HTTP Smoke Test

One command to deploy and verify all pages return HTTP 200.

```bash
./scripts/deploy-verify.sh /tmp/my-project / /search /explore /map
```

**Output** (JSON):
```json
{"phase":"summary","verdict":"all_pass","pass":4,"fail":0,"total":4}
```

**Env overrides**:
- `VERCEL_FORCE=1` — bust Vercel cache
- `DEPLOY_URL=https://my-app.vercel.app` — skip deploy, just verify

## Design Principles

1. **Agent-agnostic**: No hardcoded paths, URLs, or project names
2. **JSON output**: Machine-readable for Orchestrator parsing
3. **Composable**: Each script does one thing; combine as needed
4. **No dependencies**: Pure bash + curl + git (available everywhere)
5. **Idempotent**: Safe to re-run

## Adding to Other Projects

Copy `scripts/` into your project or reference from the skill repo:
```bash
git clone https://github.com/Arslan-Z/orchestration-workflow /tmp/orch
/tmp/orch/scripts/watchdog.sh /your/worktree
```
