> **Status**: Historical. All epics in this backlog have been implemented. Retained for reference.

Below is a Scrum-ready backlog with epics and detailed tickets that implement the full "strategy factory" workflow you described (GPU generates candidates → CPU validates under stress/out‑of‑sample → controlled deployment → live monitoring + kill switches → rotation). I've written this in a way you can paste into Jira/Linear with minimal editing.

I'm assuming your repo structure and tooling from the report: Rust `mei-backtester` (GPU sweep + CPU replay), SQLite candle DBs + funding DB, `generate_config.py`, `deploy_sweep.py`, sidecar ingestion, hot-reloadable `strategy_overrides.yaml`, and you're trading Hyperliquid perps.

I'm also assuming the product goal is: "Operate a repeatable, automated system that deploys short-lived edges while enforcing strict downside controls," not "find one config forever."

Naming convention suggestion:

* Epics: AQC-E### (AI Quant Crypto)
* Tickets: AQC-### (stories/tasks)
* Priority: P0 (must), P1 (should), P2 (nice)
* Complexity: 1,2,3,5,8,13 (story points; no time estimates)
* Labels: `data`, `backtester`, `gpu`, `validation`, `engine`, `risk`, `ops`, `observability`

Definition of Done (global, apply to all tickets):

* Code merged to main with tests (where applicable)
* Repro steps documented (README/runbook updated)
* Artifacts/logging present so behaviour is auditable
* Safe failure modes (no "silently proceeds" in trading-critical paths)

---

EPIC AQC-E100: Product framing, governance, and "what success means"
Goal: make sure the team is optimising for live survivability and repeatability, not backtest vanity.

AQC-101 (P0, 3) Define success metrics + guardrails for the system
Description: Document a short list of operational metrics and risk limits that define "working."
Acceptance criteria:

* A one-page doc in repo (e.g., `docs/success_metrics.md`) specifying:

  * Live max daily loss limit, max equity drawdown, max leverage exposure guidelines
  * Minimum trade count thresholds for evaluation windows
  * Promotion criteria (paper → live)
  * Rotation criteria (when to retire a config)
    Dependencies: none.
    Parallel: yes (independent).

AQC-102 (P0, 2) Create a strategy lifecycle state machine spec
Description: Define states: `candidate → validated → paper → live_small → live_full → paused → retired`.
Acceptance criteria:

* State diagram + transitions + triggers written and reviewed
* Each trigger is measurable from logs/metrics (no subjective triggers)
  Dependencies: AQC-101.
  Parallel: yes.

AQC-103 (P1, 3) Establish coding + review rules for trading-critical changes
Description: Require review from "risk owner" on kill-switch, sizing, order logic changes.
Acceptance criteria:

* CODEOWNERS or equivalent enforced
* Checklist added to PR template for risk-impacting changes
  Dependencies: none.
  Parallel: yes.

AQC-104 (P1, 5) Build a "runbook" skeleton for ops and incident handling
Description: When the bot misbehaves, what do we do?
Acceptance criteria:

* `docs/runbook.md` includes: pause trading, roll back config, verify DB, rerun validation, restart services
  Dependencies: none.
  Parallel: yes.

---

EPIC AQC-E200: Data foundation (candles + funding) and longer history
Goal: stop flying blind with only 12–19 days of 3m/5m data; ensure integrity and continuity.

AQC-201 (P0, 5) Data freshness + gap detection job for all candle DBs
Description: Add a script that checks per-interval/per-symbol last timestamp, missing ranges, and bar counts.
Acceptance criteria:

* Script outputs JSON + human summary
* Non-zero exit code if gaps exceed threshold
* Emits "OK"/"WARN"/"FAIL" status per DB
  Dependencies: none.
  Parallel: yes.

AQC-202 (P0, 3) Funding DB freshness verification + anomaly checks
Description: Check latest funding timestamp, missing hours, outliers.
Acceptance criteria:

* Script flags missing ranges and suspicious spikes
* Produces machine-readable output for pipeline gating
  Dependencies: none.
  Parallel: yes.

AQC-203 (P0, 8) Modify sidecar/ingestion to retain append-only history beyond 5000 bars
Description: Current "HL retains 5000 bars" shouldn't cap your stored history. Ensure you append new bars and never truncate (or archive old partitions).
Acceptance criteria:

* 3m and 5m DBs grow beyond 5000 bars per symbol
* No duplicates (unique constraint on `(symbol, time)` or equivalent)
* Documented migration steps (schema changes if needed)
  Dependencies: AQC-201.
  Parallel: mostly yes (can start now).

AQC-204 (P1, 5) Implement DB partitioning/archival strategy for large history
Description: Avoid gigantic single SQLite files and improve query speed. Options: monthly partition DBs or maintain indices.
Acceptance criteria:

* Chosen approach documented
* Queries used by backtester remain fast
* Auto-scope and loaders work across partitions (or a unified view)
  Dependencies: AQC-203.
  Parallel: yes.

AQC-205 (P1, 3) Add "universe change" tracking to reduce survivorship bias
Description: Track when symbols appear/disappear in HL universe and store metadata.
Acceptance criteria:

* A table (or file) recording symbol listing/delisting dates
* Backtests can optionally filter to symbols active during the tested period
  Dependencies: AQC-203 (recommended).
  Parallel: yes.

AQC-206 (P2, 8) Add optional orderbook snapshot storage for later slippage modelling
Description: Store occasional BBO/OB snapshots for empirical slippage study.
Acceptance criteria:

* Configurable sampling rate
* Storage bounded (rotation)
  Dependencies: none.
  Parallel: yes.

---

EPIC AQC-E300: Backtester + replay enhancements (truth engine improvements)
Goal: make CPU replay a first-class validator (time slicing, richer metrics, friction tests).

AQC-301 (P0, 8) Add explicit time-range flags to `replay` (and optionally `sweep`)
Description: Add CLI args: `--start-ts` and `--end-ts` (ISO8601 or epoch) to force evaluation on a subrange. Must cooperate with auto-scope.
Acceptance criteria:

* `replay` can run on a specified subrange within DB coverage
* Output prints the final effective range used
* If requested range is invalid/outside coverage, fails loudly
  Dependencies: none.
  Parallel: yes (core enabler for walk-forward).

AQC-302 (P0, 5) Extend replay JSON output with per-symbol stats
Description: Add `per_symbol` results: PnL, trades, win rate, max DD, fees/slippage impact.
Acceptance criteria:

* JSON output includes per-symbol breakdown
* `total_*` fields remain unchanged
  Dependencies: none.
  Parallel: yes.

AQC-303 (P0, 5) Add a replay option for slippage override without config edits
Description: Support `--slippage-bps` CLI override (and record it in output).
Acceptance criteria:

* Slippage can be set per replay run
* Output includes `slippage_bps`
  Dependencies: none.
  Parallel: yes.

AQC-304 (P1, 8) Add trade-level CSV export for analysis
Description: Optional `--export-trades path.csv` containing time, symbol, side, entry/exit, pnl, MAE/MFE, reason codes.
Acceptance criteria:

* CSV export works deterministically
* Includes unique trade IDs
  Dependencies: AQC-301 recommended.
  Parallel: yes.

AQC-305 (P1, 5) Standardize "reason codes" for exits/entries in CPU engine
Description: Useful for debugging why configs degrade live.
Acceptance criteria:

* Enumerated reason codes (stop, tp, trail, filter_exit, funding_exit, etc.)
* Included in JSON and trade CSV export
  Dependencies: AQC-304 (or vice versa).
  Parallel: yes.

AQC-306 (P1, 13) GPU/CPU parity test harness (unit + integration)
Description: For a small fixed dataset and fixed config, compare GPU sweep result to CPU replay (within tolerances).
Acceptance criteria:

* Automated test that runs in CI (CPU-only) with small fixture dataset
* Documents known divergence causes, sets guardrails
  Dependencies: AQC-302 recommended.
  Parallel: yes (but heavier).

AQC-307 (P2, 13) Optional: improve GPU kernel realism (sub-bar exits / f64 accumulation)
Description: Big-ticket parity work. Only do if needed after pipeline is stable.
Acceptance criteria:

* Defined measurable reduction in GPU/CPU divergence
  Dependencies: AQC-306.
  Parallel: later.

---

EPIC AQC-E400: Strategy factory orchestrator (nightly pipeline end-to-end)
Goal: one command produces sweeps → configs → validations → ranked shortlist → paper deploy candidate.

AQC-401 (P0, 8) Create `factory_run.py` orchestrator (single entrypoint)
Description: A script that runs the entire workflow with a run_id and stores artifacts.
Acceptance criteria:

* `python3 factory_run.py --run-id ...` runs:

  * data checks (AQC-E200 outputs)
  * GPU sweeps (selected combos)
  * config generation (top N)
  * CPU validations (suite)
  * final ranked report + recommended config(s)
* Produces an artifacts directory keyed by run_id
  Dependencies: AQC-201, AQC-202, AQC-301, AQC-303.
  Parallel: can start now with stubs.

AQC-402 (P0, 5) Sweep runner module with guardrails (only "safe" combos)
Description: Encode your discovered constraint: GPU sweep only used for ≤19d windows unless explicitly overridden.
Acceptance criteria:

* Default allowed combos: (30m/5m, 1h/5m, 30m/3m, 1h/3m)
* Requires an explicit flag to run 15m+ / 30m+ sub-bars
* Logs the auto-scoped period length each run
  Dependencies: AQC-401.
  Parallel: yes.

AQC-403 (P0, 5) Config shortlist generator (top by DD + balanced)
Description: Automate `generate_config.py` across multiple sort modes and ranks.
Acceptance criteria:

* Generates e.g. top 10 DD + top 10 balanced per sweep output
* Deduplicates configs by hash (avoid minor float noise duplicates)
  Dependencies: AQC-401.
  Parallel: yes.

AQC-404 (P1, 5) Add "repro metadata" capture for every run
Description: Record git commit, binary versions, CUDA/driver info, seeds, CLI args.
Acceptance criteria:

* `run_metadata.json` stored per run_id
* Every produced config references originating sweep and validation outputs
  Dependencies: AQC-401.
  Parallel: yes.

AQC-405 (P1, 3) Add pipeline resume/retry support
Description: If a run crashes halfway, resume from artifacts.
Acceptance criteria:

* Steps are idempotent
* `--resume` skips completed stages
  Dependencies: AQC-401.
  Parallel: yes.

AQC-406 (P1, 3) Add "smoke mode" for fast daily runs
Description: Lower trials + fewer candidates for weekdays.
Acceptance criteria:

* `--profile smoke|daily|deep` controls trials and candidate counts
  Dependencies: AQC-401.
  Parallel: yes.

AQC-407 (P2, 5) Add compute resource throttles / scheduling safety
Description: Avoid Windows TDR issues and avoid trading-engine interference.
Acceptance criteria:

* Orchestrator checks GPU availability and can defer/exit if engine is running GPU tasks
  Dependencies: AQC-401.
  Parallel: later.

---

EPIC AQC-E500: Validation suite (walk-forward, stress, robustness scoring)
Goal: stop deploying "lucky" configs. Make selection data-driven with out-of-sample pressure.

AQC-501 (P0, 8) Implement walk-forward validation runner
Description: Given a config and a date range, run multiple train/test splits. (Even if you don't "train" in replay, you can treat the sweep window as train and separate test windows.)
Acceptance criteria:

* Defines a configurable set of splits for 12–19 day windows
* Produces per-split metrics and aggregated score
  Dependencies: AQC-301.
  Parallel: yes.

AQC-502 (P0, 5) Add slippage stress matrix (10/20/30 bps)
Description: For each candidate, run CPU replay under 3 friction levels and compute degradation.
Acceptance criteria:

* Outputs a "slippage fragility" metric
* Reject configs that flip sign at 20 bps (configurable)
  Dependencies: AQC-303, AQC-401.
  Parallel: yes.

AQC-503 (P0, 5) Add concentration / diversification checks
Description: Use per-symbol breakdown (AQC-302) to compute concentration metrics.
Acceptance criteria:

* Compute: %PnL top1 symbol, top5 symbols, number of symbols traded, long/short contribution
* Threshold-based rejection rules in config
  Dependencies: AQC-302.
  Parallel: yes.

AQC-504 (P0, 5) Define and implement a single "stability score" ranking formula
Description: One scalar score to rank candidates, prioritizing robust OOS + low DD + low fragility.
Acceptance criteria:

* Score formula versioned (`score_v1`)
* Report shows components + final score
  Dependencies: AQC-501, AQC-502, AQC-503.
  Parallel: yes (can draft formula earlier).

AQC-505 (P1, 8) Add "parameter sensitivity" sanity check
Description: Take top config and perturb key axes slightly (e.g., ±1 on EMA windows, ±0.1 ATR multipliers) to see if edge vanishes.
Acceptance criteria:

* Automated perturbation set
* Produces a "sensitivity" metric
  Dependencies: AQC-401, AQC-301.
  Parallel: yes.

AQC-506 (P1, 8) Add Monte Carlo / bootstrap on trade outcomes (optional)
Description: Shuffle trade sequence or resample to estimate distribution of DD and returns.
Acceptance criteria:

* Produces confidence intervals for DD and return
  Dependencies: AQC-304 recommended.
  Parallel: yes.

AQC-507 (P1, 5) Create reject-reason reporting ("why this config was rejected")
Description: For each candidate, output human-readable reasons (e.g., "fails 20 bps stress," "too concentrated," "OOS negative").
Acceptance criteria:

* `validation_report.md` includes reasons per candidate
  Dependencies: AQC-401, AQC-504.
  Parallel: yes.

AQC-508 (P2, 8) Add "cross-universe" validation (subset of symbols)
Description: Validate on top-liquidity subset vs full universe to see if edge depends on illiquid tails.
Acceptance criteria:

* Configurable symbol sets
* Report comparison
  Dependencies: AQC-302.
  Parallel: later.

---

EPIC AQC-E600: Strategy registry, artifact storage, and reproducibility
Goal: every live deployment is traceable to a run_id, a sweep file, and a validation report.

AQC-601 (P0, 5) Create standardized artifacts directory layout
Description: Example: `artifacts/YYYY-MM-DD/run_<id>/` with subfolders for sweeps/configs/replays/reports/logs.
Acceptance criteria:

* Orchestrator writes to this layout
* README explains structure
  Dependencies: AQC-401.
  Parallel: yes.

AQC-602 (P0, 5) Implement config hashing + immutable IDs
Description: Hash the fully materialized YAML (normalized) and treat it as immutable ID.
Acceptance criteria:

* `config_id` = sha256 of normalized YAML
* Stored in reports and deployment metadata
  Dependencies: AQC-601.
  Parallel: yes.

AQC-603 (P0, 5) Build a local "registry index" (SQLite or JSONL)
Description: Index all configs and runs: metrics, dates, verdict, deployed yes/no, retirement reason.
Acceptance criteria:

* Queryable by run_id, config_id, date
* Used by deployment and reporting
  Dependencies: AQC-601, AQC-602.
  Parallel: yes.

AQC-604 (P1, 3) Add artifact retention policy + pruning
Description: Keep deep artifacts N days, keep summaries forever.
Acceptance criteria:

* Configurable retention settings
* Safe pruning (never delete deployed configs or their proofs)
  Dependencies: AQC-603.
  Parallel: yes.

AQC-605 (P1, 5) Add "reproduce this result" command
Description: Given a run_id, rerun the same replay/validation steps.
Acceptance criteria:

* `python3 factory_run.py --reproduce run_id`
  Dependencies: AQC-401, AQC-603.
  Parallel: yes.

---

EPIC AQC-E700: Deployment pipeline (paper → live) with safe rollouts
Goal: remove manual, error-prone promotion; enforce gating.

AQC-701 (P0, 5) Implement "paper deploy" command that installs a selected config safely
Description: Takes config_id, writes to paper-trading overrides, triggers engine reload/restart as needed, logs deployment event.
Acceptance criteria:

* Deployment is atomic (no partial writes)
* Produces `deploy_event.json` with who/what/when/why
  Dependencies: AQC-603.
  Parallel: yes (engine integration needed).

AQC-702 (P0, 8) Add promotion gating: validation pass + paper minimums
Description: Define conditions: "paper ran X trades or Y hours; PF > threshold; slippage within bound; no kill events."
Acceptance criteria:

* Promotion script refuses if gates not met
* Gate values configurable
  Dependencies: AQC-701, AQC-801 (monitoring metrics).
  Parallel: partial.

AQC-703 (P0, 5) Live rollout ramp (position sizing multiplier)
Description: Start live at reduced size (e.g., 0.25x), then step up automatically if healthy.
Acceptance criteria:

* Engine supports a size multiplier
* Multiplier changes are logged and visible in metrics
  Dependencies: engine support; AQC-801.
  Parallel: yes.

AQC-704 (P0, 5) Rollback mechanism (last-known-good config)
Description: Keep a "golden" fallback config for emergency and automate rollback.
Acceptance criteria:

* `rollback_to_last_good` command
* Records rollback reason
  Dependencies: AQC-603.
  Parallel: yes.

AQC-705 (P1, 5) Add "interval change orchestration" (30m main requires restart)
Description: Automate safe restart and WS resubscribe when changing main interval.
Acceptance criteria:

* Restart is graceful
* Bot comes back with correct subscriptions
* If restart fails, bot remains paused
  Dependencies: your engine controls; AQC-701.
  Parallel: yes.

AQC-706 (P1, 3) Add deployment dry-run validation
Description: Validate YAML schema + required fields before deploying.
Acceptance criteria:

* Fails fast if config invalid
  Dependencies: AQC-602.
  Parallel: yes.

---

EPIC AQC-E800: Live risk controls and kill switches (hard + soft)
Goal: survive inevitable regime shifts and bad fills. This is where "earning money" becomes "not losing it all."

AQC-801 (P0, 8) Implement structured event logging in trading engine
Description: Emit machine-readable events for: order placed, filled, rejected, position opened/closed, kill switch triggered, mode changed.
Acceptance criteria:

* Events are written to JSONL with stable schema version
* Includes timestamps, symbol, config_id, run_id
  Dependencies: none.
  Parallel: yes.

AQC-802 (P0, 8) Equity drawdown kill switch (peak-to-valley)
Description: If DD exceeds threshold, bot pauses new entries and optionally closes positions according to policy.
Acceptance criteria:

* Configurable threshold
* Clear behaviour: "pause entries" and "reduce risk"
* Emits kill event and requires explicit resume condition
  Dependencies: AQC-801.
  Parallel: yes.

AQC-803 (P0, 5) Daily loss limit kill switch (UTC day)
Description: Track realized PnL per UTC day; stop if below threshold.
Acceptance criteria:

* Reset at UTC day boundary
* Emits kill event
  Dependencies: AQC-801.
  Parallel: yes.

AQC-804 (P0, 8) Slippage anomaly guard
Description: If live slippage exceeds stress-tested expectations (e.g., > X bps median over last N fills), pause.
Acceptance criteria:

* Computes live slippage from fills vs mid/BBO
* Triggers pause and logs
  Dependencies: AQC-801.
  Parallel: yes.

AQC-805 (P1, 5) "Performance degradation" soft stop
Description: Rolling PF/WR/Sh (over last N trades or last T hours). If below threshold, pause or switch to conservative mode.
Acceptance criteria:

* Configurable windows and thresholds
* Avoids triggering with too few trades (min sample)
  Dependencies: AQC-801.
  Parallel: yes.

AQC-806 (P1, 8) Portfolio heat limit (risk budget)
Description: Cap total open risk (e.g., sum of per-position stop distance * size) as % of equity.
Acceptance criteria:

* New entries rejected if heat > limit
* Logged decisions
  Dependencies: engine position model; AQC-801.
  Parallel: yes.

AQC-807 (P1, 5) Exposure concentration limit (max correlated bets)
Description: Limit number of same-direction positions in highly correlated assets; optionally use BTC beta proxy.
Acceptance criteria:

* Simple first version: cap max simultaneous longs/shorts in "alts" bucket
* Logs when signals are skipped due to exposure rules
  Dependencies: AQC-801.
  Parallel: yes.

AQC-808 (P2, 8) Emergency "flat now" command + safe unwind policy
Description: For incidents, flatten positions with a defined policy.
Acceptance criteria:

* One command triggers flatten and pause
* Policy documented and tested in paper
  Dependencies: engine capabilities.
  Parallel: later.

---

EPIC AQC-E900: Observability, dashboards, and daily reporting
Goal: turn this into an auditable production system with rapid feedback.

AQC-901 (P0, 5) Daily summary report generator (paper + live)
Description: Generate a daily markdown/HTML report with key metrics, config_id, kill events, PnL, DD, slippage.
Acceptance criteria:

* Runs from logs + registry
* Stored under artifacts
  Dependencies: AQC-603, AQC-801.
  Parallel: yes.

AQC-902 (P0, 5) Real-time health dashboard (minimal viable)
Description: A simple local web UI or terminal dashboard showing: current mode, config_id, open positions, today PnL, DD, last data timestamp.
Acceptance criteria:

* Updates at least every 10s
* Clearly shows "PAUSED" state
  Dependencies: AQC-801.
  Parallel: yes.

AQC-903 (P1, 8) Metrics export (Prometheus or JSON aggregator)
Description: Standard metrics endpoint for Grafana or similar.
Acceptance criteria:

* Exposes counters/gauges: orders, fills, slippage, PnL, DD, kill events
  Dependencies: AQC-801.
  Parallel: yes.

AQC-904 (P1, 5) Alerting (Telegram/Discord/email) on critical events
Description: Notify on pause/kill, restart, failed nightly pipeline, data gaps.
Acceptance criteria:

* Alerts triggered only on state changes (avoid spam)
* Configurable channels
  Dependencies: AQC-201, AQC-401, AQC-802/803.
  Parallel: yes.

AQC-905 (P2, 8) Post-trade analytics notebook pack
Description: Prebuilt analysis scripts for MAE/MFE, symbol contribution, entry/exit reasons.
Acceptance criteria:

* Works from trade CSV + events
  Dependencies: AQC-304, AQC-801.
  Parallel: later.

---

EPIC AQC-E1000: Regime detection + mode switching (trend vs chop) and strategy ensemble
Goal: stop trading when the strategy's assumptions are false; optionally run multiple modes.

AQC-1001 (P1, 8) Implement "regime gate v1" using existing breadth/ADX/vol metrics
Description: Define a binary gate: trade only when regime is "trend OK."
Acceptance criteria:

* Gate is computed on schedule (e.g., every main bar)
* Trades are blocked when gate is off
* Gate state logged and visible in dashboard
  Dependencies: AQC-801.
  Parallel: yes.

AQC-1002 (P1, 5) Mode switching policy (Primary/Fallback/Conservative/Flat)
Description: Encode your three-mode plan: 30m/5m DD ↔ 1h/5m DD ↔ 1h/15m DD (or flat).
Acceptance criteria:

* Automatic switching based on triggers (kill events, performance degradation)
* Switch events logged with reason
  Dependencies: AQC-805, AQC-701.
  Parallel: yes.

AQC-1003 (P2, 13) Add ensemble runner (2–3 strategies concurrently)
Description: Run multiple configs with risk budgeting across them (not 20 correlated positions each).
Acceptance criteria:

* Each strategy has an allocation budget
* Global heat/exposure caps enforced across strategies
  Dependencies: AQC-806, AQC-807.
  Parallel: later.

AQC-1004 (P2, 8) Research pipeline for new strategy archetypes (mean reversion, funding arb)
Description: Scaffold new "strategy modules" that plug into the same factory pipeline.
Acceptance criteria:

* Template for a new strategy with backtest hooks
* Can be validated with same suite
  Dependencies: AQC-E500/E600 stable.
  Parallel: later.

---

EPIC AQC-E1100: CI/CD, testing, and ops hardening
Goal: make changes safe, repeatable, and less fragile under WSL2/GPU constraints.

AQC-1101 (P0, 5) Add config schema validation + type coercion tests
Description: Ensure YAML parsing and coercion rules are locked and tested.
Acceptance criteria:

* Unit tests for coercion (int/bool/enum rounding)
* CI fails if config schema breaks
  Dependencies: none.
  Parallel: yes.

AQC-1102 (P0, 5) Add integration test: "factory smoke run" on fixture dataset
Description: Run minimal pipeline on a small dataset (CPU-only) to ensure orchestration doesn't break.
Acceptance criteria:

* CI job completes and produces artifacts
  Dependencies: AQC-401.
  Parallel: yes.

AQC-1103 (P1, 8) Build/release automation for `mei-backtester` binaries (CPU + GPU)
Description: Standardize how binaries are built and versioned; store build metadata.
Acceptance criteria:

* Version stamped into binary
* Pipeline records build info in run_metadata
  Dependencies: AQC-404.
  Parallel: yes.

AQC-1104 (P1, 5) System service management (systemd/cron) for nightly runs + engine
Description: Ensure nightly pipeline runs reliably and logs are rotated.
Acceptance criteria:

* Service/timer definitions in repo
* Logs rotated and retained per policy
  Dependencies: AQC-401.
  Parallel: yes.

AQC-1105 (P2, 8) Secrets management for alerting channels / API keys
Description: Avoid secrets in repo; use environment or vault.
Acceptance criteria:

* Documented setup
* No secrets committed
  Dependencies: AQC-904.
  Parallel: yes.

---

What can be done in parallel (workstreams + dependency notes)

Workstream 1: Data reliability and history (can run mostly parallel)

* AQC-E200 (data checks + append-only retention) can start immediately.
* Minimal dependencies: none. This is a high-leverage track because longer 3m/5m history improves every other epic's signal-to-noise ratio.

Workstream 2: Replay enhancements (parallel, but critical-path enabling)

* AQC-301/302/303 are blockers for serious validation. Start them immediately.
* These can be developed in parallel with orchestrator scaffolding by stubbing outputs.

Workstream 3: Orchestrator + artifacts/registry (parallel)

* AQC-E400 and AQC-E600 can start early even while replay features are landing (mock data).
* Once replay features are ready, plug them in.

Workstream 4: Validation suite (depends on replay time slicing + per-symbol stats)

* AQC-501 needs AQC-301.
* AQC-503 needs AQC-302.
* AQC-502 needs AQC-303.
* The scoring (AQC-504) and reject reporting (AQC-507) can be designed in parallel and integrated after.

Workstream 5: Engine risk controls + logging (parallel with everything; also critical path)

* AQC-E800 can begin immediately.
* AQC-801 (event logging) is a dependency for dashboards and promotion gating, but you can implement kill switches in parallel if you ensure they also emit events.

Workstream 6: Deployment & promotion (depends on registry + engine events)

* AQC-701 can start once registry basics exist (AQC-603) and engine can consume config_id/run_id.
* Promotion gating (AQC-702) should wait until events + daily reports exist.

Workstream 7: Observability (depends on event logging)

* AQC-901/902 can start once AQC-801 exists (even with minimal events).

Workstream 8: Regime switching and ensemble (do after stability)

* AQC-E1000 is best tackled after kill switches + pipeline are stable, otherwise you'll add complexity before you can trust the basics.

Critical path (the shortest chain to a safe end-to-end system)

1. AQC-201/202 (data gating)
2. AQC-301/303/302 (replay time range + slippage override + per-symbol metrics)
3. AQC-401/403/601/603 (orchestrator + shortlist + artifacts + registry)
4. AQC-502/503/504 (stress tests + concentration + score)
5. AQC-801/802/803 (events + core kill switches)
6. AQC-701 (paper deploy) → AQC-901 (daily report)
   Then you have a loop that can run daily without blowing up silently.

Suggested initial "Sprint 1" scope (if you want a coherent first deliverable)

* Data gates: AQC-201, AQC-202
* Replay enablers: AQC-301, AQC-303, AQC-302
* Event logging: AQC-801
* Orchestrator skeleton + artifacts: AQC-401, AQC-601
  Deliverable: one command that runs checks + a replay suite on an existing config and produces a report + artifacts.

Suggested "Sprint 2" scope (turn it into the strategy factory)

* Sweep runner + config shortlist: AQC-402, AQC-403
* Validation suite core: AQC-501, AQC-502, AQC-503, AQC-504, AQC-507
* Kill switches core: AQC-802, AQC-803
  Deliverable: nightly run produces ranked shortlist with reject reasons and can auto-pause trading if limits hit.

Suggested "Sprint 3" scope (controlled deployment)

* Paper deploy: AQC-701
* Rollback: AQC-704
* Ramp: AQC-703
* Daily report + minimal dashboard: AQC-901, AQC-902
  Deliverable: paper→live workflow with guardrails and observability.

If you want, I can also provide a Jira import-friendly CSV outline (Epic, Issue Type, Summary, Description, Acceptance Criteria, Priority, Points, Dependencies, Labels).
