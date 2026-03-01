# SSOT Trust Chain, Step 4 Recovery, and Factory-Cycle Stabilisation

Date: 2026-02-21  
Owner: AI Quant team  
Scope: Current repository state, trust model, last 4-day work summary, factory-cycle issues, recovery plan, and expected outcomes.

---

## 1. Executive summary

The delivery pipeline is operational end-to-end, but confidence in GPU output is still blocked by Step 4 parity quality.

Current truth:

1. Step 1 to Step 3 can run at full scale on GPU.
2. Step 5 to Step 6 flow mechanics are functional.
3. Step 4 (GPU to CPU validation) remains the trust bottleneck.
4. We have fixed specific deterministic divergences, but we must now enforce strict comparison contracts to prevent false regression signals.

The trust model is unchanged and must remain strict:

1. Live trading is the highest-trust ground truth.
2. Paper must simulate Live.
3. CPU backtester must replay Live/Paper semantics.
4. GPU must align to CPU under identical contracts.

---

## 2. Critique of the previous draft

The previous write-up was directionally correct but not decision-complete. Its key weaknesses were:

1. It mixed strategic statements with insufficient operational constraints.
2. It did not define a hard artefact-level benchmark contract.
3. It did not explicitly separate workflow health from trust health.
4. It lacked a strict regression policy for invalid comparisons.
5. It did not clearly codify the acceptance gate required before reducing CPU validation burden.

This document addresses these gaps.

---

## 3. Current repository and workflow situation

## 3.1 Pipeline status by factory step

Factory lifecycle (target model):

1. Sweep 1M (GPU).
2. Top 1000 by PnL shortlist pool.
3. Top 10 per channel (efficient, growth, conservative).
4. CPU validation against shortlisted candidates.
5. Gate and selection.
6. Deploy and follow-up stages.

Current practical state:

1. Steps 1 to 3 are executable and producing candidates.
2. Steps 5 to 6 are executable as process flow.
3. Step 4 parity evidence is the unresolved quality gate.

## 3.2 Why recent “worse” numbers appeared

A major measurement error occurred in reporting:

1. GPU reference metrics were taken from an older run context.
2. CPU replay was re-run with a different binary build and a different effective data window.
3. Those results were compared as if they were equivalent.

This is an invalid comparison and must be treated as `INVALID_COMPARISON`, not as performance regression.

---

## 4. Chain of trust and SSOT interpretation

## 4.1 Trust order

1. Live
2. Paper
3. CPU backtester
4. GPU

## 4.2 SSOT implications

1. Decision SSOT is Rust decision logic.
2. Python may remain as orchestration/runtime envelope, but not as decision truth authority.
3. GPU is an acceleration target and must prove equivalence to CPU under controlled contracts.

## 4.3 Practical governance

1. No GPU claim is accepted without CPU parity evidence under the same contract.
2. No “pipeline green” message is allowed to imply “GPU trusted”.

---

## 5. Work completed in the last four days

## 5.1 Alignment and parity investigations

1. Repeated deep tracing of CPU/GPU mismatches at symbol/timestamp/event level.
2. Multiple focused axis parity rechecks using sub-bar scenarios (`30m` main with `3m` entry/exit).
3. Cause classification tightened around `STATE_MACHINE` versus `REDUCTION_ORDER`.

## 5.2 Deterministic parity fix merged

PR #817 (merged):

1. GPU now refreshes post-exit same-direction cooldown (PESC) state on partial closes.
2. This aligns GPU behaviour with CPU semantics where partial close updates post-exit cooldown context.
3. A known `STATE_MACHINE` divergence case moved to `trade_delta=0` with only residual reduction-order drift.

## 5.3 Factory-cycle hardening and control-flow fixes

Recently merged factory-focused changes include:

1. Baseline lifecycle and replay contract fingerprinting support.
2. Factory-cycle deploy-note fault handling fix.
3. Promotion gate timing logic against pre-deploy windows.
4. Promotion-before-deploy flow correction.

These improve process robustness, but they do not by themselves prove Step 4 parity quality.

---

## 6. Factory-cycle issues we faced

## 6.1 Measurement contamination

The biggest blocker was not pure strategy quality; it was evidence integrity.

Observed failure mode:

1. Candidate metrics and replay outputs were compared across different contracts.
2. Binary and data-window drift produced exaggerated deltas.
3. This created false conclusions about regression severity.

## 6.2 Workflow-status versus trust-status confusion

1. The pipeline can complete operationally while Step 4 trust remains weak.
2. Without explicit trust reporting, this appears as success when it is not trust-complete.

## 6.3 Remaining technical mismatch classes

1. `STATE_MACHINE` must always be prioritised and eliminated first.
2. `REDUCTION_ORDER` residuals are second-phase tightening after trade-count parity is stable.

---

## 7. Benchmark and regression policy (mandatory)

## 7.1 Step 4 benchmark contract

Every Step 4 report must include a single immutable comparison contract with:

1. `code_commit` and binary fingerprint.
2. Data snapshot fingerprint for candles and funding.
3. Exact replay window (`from_ts`, `to_ts`).
4. Universe set fingerprint.
5. Candidate config set fingerprint (all 30).
6. Runtime parameters fingerprint (intervals, funding mode, balance source).

## 7.2 Invalid comparison rule

If any contract field differs between GPU and CPU evidence:

1. Mark result as `INVALID_COMPARISON`.
2. Exclude it from all progress KPIs.
3. Do not treat it as improvement or regression.

## 7.3 Strict progression thresholds (agreed)

Step 4 passes only when all conditions hold:

1. `30/30 trade_delta = 0`
2. `mean_abs_delta_pnl_pp <= 0.10`
3. `mean_abs_delta_dd_pp <= 0.10`
4. `STATE_MACHINE count = 0`

Promotion of trust status requires:

1. Three consecutive cycles meeting the strict thresholds.

---

## 8. Forward plan

## 8.1 Phase A: measurement reset and contract lock

1. Produce `step4_contract.json` for the active 30-candidate set.
2. Re-run CPU and GPU under the exact same contract only.
3. Publish a clean baseline report.

Deliverables:

1. `step4_contract.json`
2. `step4_compare.tsv`
3. `step4_aggregate.json`
4. `step4_mismatch_breakdown.json`

## 8.2 Phase B: eliminate STATE_MACHINE first

1. Rank mismatches by frequency and impact.
2. Patch one root cause per atomic PR.
3. Mandatory reviewer subagent review before merge.
4. Re-run exactly the same contract after each merge.

Success criterion:

1. `STATE_MACHINE = 0` across all 30 candidates.

## 8.3 Phase C: tighten REDUCTION_ORDER residuals

1. Focus on ordering and micro-price residual causes.
2. Maintain zero trade-count delta while reducing PnL/DD residuals.
3. Keep strict contract invariants unchanged during comparisons.

Success criterion:

1. Strict threshold compliance across all KPI fields.

## 8.4 Phase D: trust graduation policy

1. Keep CPU validation as a hard gate until strict pass is achieved in 3 consecutive cycles.
2. After graduation, CPU validation can move to sampling mode with periodic full checks.

---

## 9. Expected outcomes

Short-term expected outcomes:

1. No further false-regression reports from mixed comparisons.
2. Reproducible and audit-safe Step 4 evidence.
3. Deterministic mismatch prioritisation and faster closure.

Mid-term expected outcomes:

1. Stable zero trade-count deltas across shortlisted candidates.
2. Residual PnL/DD drift reduced to strict thresholds.
3. Reliable GPU candidate trust for factory decisioning.

Long-term expected outcomes:

1. End-to-end nightly cycle with explicit trust semantics.
2. Management-grade evidence for Live expansion decisions.
3. Sustained SSOT integrity across Live, Paper, CPU, and GPU layers.

---

## 10. Non-negotiable operating rules

1. No parity claim without a valid contract.
2. No regression claim from invalid comparison artefacts.
3. No interpretation of Step 1 to Step 3 completion as Step 4 trust completion.
4. No trust-status ambiguity in release and promotion reporting.

---

## 11. Immediate next execution block

1. Lock and publish one Step 4 contract for the current 30 candidates.
2. Re-run CPU and GPU under that contract.
3. Publish clean baseline KPI.
4. Patch top `STATE_MACHINE` cause if present; otherwise move to `REDUCTION_ORDER`.
5. Repeat until strict gate is met for three consecutive cycles.

