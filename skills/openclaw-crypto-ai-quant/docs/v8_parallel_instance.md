# Parallel Paper Instance Deployment

This document describes how to run a fully isolated paper instance in parallel with the production `master` deployment, including a nightly factory cycle (sweep → validate → deploy).

The parallel instance is intentionally namespaced:

- systemd unit names end with a suffix (e.g. `-v8`)
- WS sidecar socket is `%t/openclaw-ai-quant-ws-v8.sock`
- monitor port is separate (e.g. `61018`)

## Safety Rules

1. Do not switch branches inside the live production working directory.
2. Do not reuse production sockets/ports for the parallel instance.
3. Do not overwrite production binaries in `~/.local/bin/`.

## 1. Create a Dedicated Runtime Worktree

Use a long-lived worktree so the factory/deploy loop can modify it without polluting your dev checkout.

```bash
git worktree add ~/openclaw-plugins/ai_quant_wt/parallel-runtime origin/master
cd ~/openclaw-plugins/ai_quant_wt/parallel-runtime
uv sync --dev
```

## 2. Build Binaries

### WS Sidecar

```bash
cd ws_sidecar
cargo build --release
install -m 0755 target/release/openclaw_ai_quant_ws_sidecar ~/.local/bin/openclaw-ai-quant-ws-sidecar-v8
```

### Backtester (GPU)

```bash
cd ~/openclaw-plugins/ai_quant_wt/parallel-runtime
python3 tools/build_mei_backtester.py --gpu
```

## 3. Configure Environment Files

Copy from the example templates and edit:

```bash
cp systemd/ai-quant-universe-v8.env.example ~/.config/openclaw/ai-quant-universe-v8.env
cp systemd/ai-quant-v8.env.example ~/.config/openclaw/ai-quant-v8.env
cp systemd/ai-quant-monitor-v8.env.example ~/.config/openclaw/ai-quant-monitor-v8.env
```

Key configuration:

- `~/.config/openclaw/ai-quant-universe-v8.env` — symbols / intervals
- `~/.config/openclaw/ai-quant-v8.env` — Discord channel, kill-switch file, retention
- `~/.config/openclaw/ai-quant-monitor-v8.env` — bind address + port

## 4. Install systemd User Units

```bash
PROJECT_DIR=~/openclaw-plugins/ai_quant_wt/parallel-runtime
mkdir -p ~/.config/systemd/user

for f in systemd/openclaw-ai-quant-*-v8.*.example; do
  out=~/.config/systemd/user/$(basename "$f" .example)
  sed "s|\\$PROJECT_DIR|$PROJECT_DIR|g" "$f" > "$out"
done

systemctl --user daemon-reload
```

### Per-Instance Strategy YAML

Create separate configs for candidate lanes and the proven lane:

```bash
cp "$PROJECT_DIR/config/strategy_overrides.yaml" "$PROJECT_DIR/config/strategy_overrides.paper1.yaml"
cp "$PROJECT_DIR/config/strategy_overrides.yaml" "$PROJECT_DIR/config/strategy_overrides.paper2.yaml"
cp "$PROJECT_DIR/config/strategy_overrides.yaml" "$PROJECT_DIR/config/strategy_overrides.paper3.yaml"
cp "$PROJECT_DIR/config/strategy_overrides.yaml" "$PROJECT_DIR/config/strategy_overrides.livepaper.yaml"
```

Set each trader service to its own YAML via `AI_QUANT_STRATEGY_YAML`.

The factory service should run with `--candidate-count 3`, `--candidate-services`, and `--candidate-yaml-paths` for the candidate lanes.

### Enable and Start

```bash
systemctl --user enable --now openclaw-ai-quant-ws-sidecar-v8.service
systemctl --user enable --now openclaw-ai-quant-trader-v8-paper1.service
systemctl --user enable --now openclaw-ai-quant-monitor-v8.service
systemctl --user enable --now openclaw-ai-quant-funding-v8.timer
systemctl --user enable --now openclaw-ai-quant-factory-v8.timer
systemctl --user enable --now openclaw-ai-quant-prune-runtime-logs-v8.timer
```

## 5. Observe

Monitor UI:

```
http://127.0.0.1:61018/
```

Logs:

```bash
journalctl --user -u openclaw-ai-quant-ws-sidecar-v8.service -f
journalctl --user -u openclaw-ai-quant-trader-v8-paper1.service -f
journalctl --user -u openclaw-ai-quant-factory-v8.service -f
```

Artifacts:

- `artifacts/YYYY-MM-DD/run_<run_id>/`
- `artifacts/registry/registry.sqlite`
- `artifacts/deployments/paper/.../deploy_event.json`
