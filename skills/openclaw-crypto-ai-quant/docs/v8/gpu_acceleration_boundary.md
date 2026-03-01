# Engine Unification Boundary and Proof Protocol

## Goal

Keep one canonical decision kernel for all execution paths while allowing GPU to remain a candidate generation accelerator.

- Canonical decision kernel: `engine/core.py` decision provider chain (Rust runtime, fallback file, explicit noop).
- Replay runner and live/paper runners consume the same decision objects (`KernelDecision`) and feed the same trader interface.
- Sweep/run runners generate candidate artefacts from the same backtester/replay outputs and can be revalidated in Python.

## What is guaranteed today

1. Kernel provider resolution
   - `AI_QUANT_KERNEL_DECISION_PROVIDER=rust` (explicit): must load Rust runtime, otherwise hard fail.
   - default mode: prefer Rust runtime; fallback to `KernelDecisionFileProvider` when a file is configured and runtime is unavailable.
   - no runtime and no file: hard fail in bootstrap, preventing silent fallback to legacy analysis paths.
2. Live/paper decision routing
   - Unified execution loop in `UnifiedEngine` uses `decision_provider.get_decisions()` for explicit actions (`OPEN`, `ADD`, `CLOSE`, `REDUCE`).
3. Replay equivalence gate
   - `tools/replay_equivalence.py` compares ordered decision traces with configurable float tolerance.
   - `factory_run.py` runs the comparator after each replay when `AI_QUANT_REPLAY_EQUIVALENCE_BASELINE` is set.

## Evidence we can produce

- Unit tests (`tests/test_kernel_decision_routing.py`) for:
  - provider auto-mode preference and fail-fast rules.
  - file fallback and noop mode behaviour.
- Unit tests (`tests/test_replay_equivalence.py`) for deterministic trace comparison and tolerance handling.
- Unit tests (`tests/test_factory_replay_harness.py`) for the factory gate integration paths.
- Candidate schema tests (`tests/test_gpu_candidate_schema.py`) against `schemas/gpu_candidate_schema.json`.

## Boundary rules (what is not part of this kernel contract)

1. Data ingress/egress, market feed quality, broker latency, and partial fill handling are execution-layer concerns.
2. GPU acceleration for sweep/TPE remains a throughput optimisation and must not be the sole source of decision promotion.

## Proof commands (required in PR review)

```bash
uv run pytest tests/test_kernel_decision_routing.py \
  tests/test_replay_equivalence.py \
  tests/test_factory_replay_harness.py \
  tests/test_gpu_candidate_schema.py
```

Replay parity check against a baseline:

```bash
export AI_QUANT_REPLAY_EQUIVALENCE_BASELINE=/path/to/baseline_replay.json
export AI_QUANT_REPLAY_EQUIVALENCE_STRICT=1
export AI_QUANT_REPLAY_EQUIVALENCE_TOLERANCE=1e-12
export AI_QUANT_REPLAY_EQUIVALENCE_MAX_DIFFS=25
python3 factory_run.py --run-id <id> ...
```

Candidate output compatibility is validated by reading/rejecting rows that do not satisfy:
`schemas/gpu_candidate_schema.json` when `--output-mode=candidate` rows are used.

## Promotion evidence that must exist before rollout

- `selection.json` must include:
  - `selection_stage = "selected"`
  - `deploy_stage = no_deploy|skipped` (dry/smoke) or not `pending` (real)
- `promotion_stage = skipped|approved` (dry/smoke) or not `pending` (real)
- `evidence_bundle_paths` with canonical file set:
  - `run_dir`
  - `run_metadata_json`
  - `selection_json`
  - `report_json`
  - `report_md`
  - `selection_md`
- `selection_gate_summary_json` (machine-readable output emitted by
  `scripts/run_factory_stage_gate.sh` or `scripts/validate_factory_selection_gate.py`)
- Selected candidate must include `canonical_cpu_verified = true` and replay proof fields:
  - `candidate_mode = true`
  - `schema_version = 1`
  - `replay_stage`
  - `replay_equivalence_report_path`
  - `replay_equivalence_status = pass`
  - `replay_equivalence_count`
- `scripts/validate_factory_selection_gate.py` is the machine-readable gate used by
  `scripts/run_factory_stage_gate.sh`; every dry/smoke/real execution must pass it.

## CPU / GPU / TPE / grid confidence level

- CPU/CUDA/TPE/Grid sweeps are considered aligned when:
  1. sweep output is emitted in shared schema (candidate/replay structure), and
  2. selected candidates are replayed through the same canonical replay path and pass comparator checks.
- This does not remove hardware-level numeric differences in non-canonical paths; it isolates all promotion decisions to the canonical path.
- GPU decision logic is generated from Rust kernel source via template-based codegen (see [gpu-codegen-guide.md](../../backtester/docs/gpu-codegen-guide.md)), ensuring SSOT alignment.
