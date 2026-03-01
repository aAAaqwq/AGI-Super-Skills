# GPU/CPU Parity Fixtures

This directory contains small, fixed fixtures used to track GPU sweep vs CPU replay drift.

The expected GPU output is generated on a CUDA machine and committed.

## What the parity test checks
- Loads `candles_1h.json` and runs a single CPU simulation using `strategy.yaml`.
- Loads `expected_gpu_sweep.json` (generated from the GPU sweep engine using the same fixture + strategy).
- Asserts that key summary metrics remain within a tolerance envelope.

This is not meant to prove exact equality. It is an early warning system when GPU and CPU drift too far apart.

## Known sources of divergence
- GPU uses `f32` accumulation and a simplified trade kernel.
- CPU uses `f64` and evaluates some conditions more precisely.
- Exit modelling differs when sub-bar candles are used (this fixture uses indicator bars only).

## Regenerating
1. (Optional) Regenerate the candle fixture from your local SQLite DB:
```bash
python3 backtester/testdata/gpu_cpu_parity/generate_candles_fixture.py \
  --db candles_dbs/candles_1h.db \
  --interval 1h \
  --symbols BTC ETH SOL \
  --limit 600 \
  --out backtester/testdata/gpu_cpu_parity/candles_1h.json
```

2. Regenerate the expected GPU output (requires CUDA + `bt-gpu` build dependencies):
```bash
cd backtester
cargo run -p bt-gpu --bin generate_parity_fixture
```

Note (WSL2): you may need to prefix the command with `LD_LIBRARY_PATH=/usr/lib/wsl/lib`.

3. Run the CPU-only parity test:
```bash
cd backtester
cargo test -p bt-core --test gpu_cpu_parity
```

4. Run the tiny GPU runtime parity fixture (requires CUDA toolkit + runtime):
```bash
cd backtester
cargo test -p bt-gpu --test gpu_runtime_parity_tiny_fixture -- --nocapture
```

## CI gate
- `scripts/ci_gpu_parity_gate.sh` is the command-level parity gate used in CI.
- It runs the tiny GPU fixture and emits an explicit warning when CUDA is unavailable.
- By default (`AQC_GPU_PARITY_STRICT=0`), CUDA-unavailable runners continue with warning-only semantics.
- Set `AQC_GPU_PARITY_STRICT=1` to fail fast when CUDA is unavailable.
- Workflow: `.github/workflows/gpu-parity-gate.yml`.
