# Strategy Module Template (AQC-1004)

This is a minimal template for creating a new strategy module that works with the current factory pipeline.

## 1. Validate The Config

```bash
python tools/deploy_validate.py --config research/strategy_modules/template/strategy.yaml
```

## 2. Run A Factory Smoke Profile

This runs the end-to-end pipeline and stores artefacts under `artifacts/<run_id>/`.

```bash
python factory_run.py \
  --run-id template_smoke_$(date +%Y%m%d_%H%M%S) \
  --profile smoke \
  --config research/strategy_modules/template/strategy.yaml \
  --sweep-spec research/strategy_modules/template/sweep.yaml
```

To use the GPU sweep path, add `--gpu` (requires CUDA build/runtime and an idle GPU).

## 3. Validation Suite Hooks

The factory pipeline already supports running additional validators. For manual validation runs, you can use:

- `tools/sensitivity_check.py` (one-at-a-time parameter perturbations)
- `tools/cross_universe_validate.py` (robustness across symbol universes)
- `tools/monte_carlo_bootstrap.py` (bootstrap resampling)

Each tool accepts `--config <path>` and produces machine-readable JSON outputs for gating.

