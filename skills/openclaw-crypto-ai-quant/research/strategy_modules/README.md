# Strategy Modules (Research Pipeline) (AQC-1004)

A **strategy module** is a self-contained directory that can be plugged into the existing factory workflow:

- GPU sweep (optional) via `mei-backtester sweep`
- CPU replay via `mei-backtester replay`
- Validation suite via the existing `tools/*.py` validators
- Reporting and artefact capture via `factory_run.py`

The intention is to make it easy to prototype new strategy archetypes (mean reversion, funding arb, etc.)
without changing the factory code-paths.

## What A Module Contains

- `strategy.yaml`: the base strategy config (YAML overlay).
- `sweep.yaml`: a sweep spec for GPU/CPU parameter search.
- `README.md`: module-specific notes and repro commands.

## Template

Start from:

- `research/strategy_modules/template/`

