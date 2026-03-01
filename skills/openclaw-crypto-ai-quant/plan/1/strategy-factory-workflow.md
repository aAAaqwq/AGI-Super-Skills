> **Status**: Implemented. The strategy factory is operational (`factory_run.py`, `tools/factory_cycle.py`). See [strategy_lifecycle.md](../../docs/strategy_lifecycle.md) and [success_metrics.md](../../docs/success_metrics.md) for the current state machine and gate thresholds.

What your report is really saying is: you already have the "alpha engine" you need, but the thing that will make (or break) your ability to earn money isn't finding *the* best config. It's building a repeatable "strategy factory" loop that (1) generates candidates fast, (2) rejects the ones that only look good in-sample, (3) deploys small with strict risk limits, and (4) rotates/pauses quickly when the edge decays.

Below is a high-level strategy and a concrete workflow you can automate using the exact components you already have (GPU TPE sweep → config generation → CPU replay → deploy).

---

First, here's the clean interpretation of your findings (this is the foundation of the workflow):

1. Your GPU sweeps are an excellent **candidate generator**, not a truth oracle.
   You proved this yourself: on ≥54-day periods, GPU and CPU disagree on the sign of PnL. That means GPU is producing "false winners" when the evaluation horizon is long and the simulation is mismatched (f32 + simplified trade logic + main-bar-only exits).

2. CPU replay (with sub-bar entry/exit) is the closest thing you have to "truth."
   So the correct posture is: GPU proposes, CPU disposes.

3. Sub-bar exits (3m/5m) are not a small detail; they are the strategy.
   Everything else (EMA windows, thresholds, etc.) is secondary compared to exit granularity and risk controls. In other words, your "edge" is partly: "manage risk intrabar, don't let coarse bars lie."

4. "Best DD" beating "Best PnL" on CPU is a giant hint about robustness.
   It usually means your system is over-optimising for lucky paths and compounding artifacts, and DD-optimisation is acting like a regulariser.

5. Your current data retention effectively forces a short-horizon business model.
   Right now, your 3m DB is 12 days and 5m DB is 19 days. That means you literally cannot validate 3m/5m strategies over months, even if the strategy might work longer. So the "2–3 week lifespan" conclusion may be partly real regime decay, and partly "you can only see 2–3 weeks."

That leads to the only high-level approach that fits your reality:

You're not building "one strategy that wins."
You're building a system that repeatedly manufactures a small, temporary edge and keeps risk bounded when the edge disappears.

---

Now the high-level strategy that's consistent with your results

A practical, automatable strategy for your setup is:

A regime-aware, risk-first momentum system with rapid rotation.

• Signal family: your existing momentum/breadth/volume-confirmed trend logic (mei_alpha_v1).
• Execution granularity: always trade with 5m (or 3m) entry/exit resolution.
• Parameter philosophy: optimise for drawdown / stability first, not peak PnL.
• Lifecycle assumption: parameters expire; treat configs as perishable.
• Risk philosophy: portfolio risk limits matter more than indicator tweaks.
• Operational model: "always-on pipeline" that continuously evaluates and swaps configs under guardrails.

This matches exactly what your best result is telling you: 30m main with 5m sub-bars + DD-optimised parameters is your current "best-known production mode."

---

The actionable, repeatable, automatable workflow

Think of it as five loops running on different clocks:

A) Data integrity loop (continuous)
B) Candidate generation loop (nightly / daily)
C) Robust validation loop (nightly, after candidate gen)
D) Deployment loop (controlled, gated)
E) Live monitoring + kill-switch loop (continuous)

I'll describe each in the way you can actually implement with your current repo.

---

A) Data integrity loop (continuous)

If this part is weak, everything downstream becomes self-deception.

1. Verify DB completeness per interval daily

* Check that each DB has the expected number of bars per symbol (or at least no sudden gaps).
* Alert if a symbol stops updating, because missing candles create phantom edges.

2. Persist more than 5000 bars going forward (if possible in your sidecar)
   Right now, you're effectively capped by HL's last-5000 retention *as stored*. The single biggest upgrade you can make to "earn money sustainably" is to turn the sidecar storage into an append-only history so your 3m/5m windows eventually become 90–180 days.

This is important because it changes your entire business model:

* With 12–19 days of data, you must rotate constantly.
* With 90–180 days of 5m data, you can actually test whether 30m/5m DD is robust across regimes.

If you do only one infrastructure upgrade, do this.

---

B) Candidate generation loop (nightly/daily)

Goal: generate a small set of candidate configs quickly, using GPU only where it's reliable.

Based on your evidence, keep GPU sweep usage inside the zone where it's directionally correct:

* Main: 30m and/or 1h
* Sub-bar: 3m or 5m
* Horizon: whatever your 3m/5m DB supports (12–19 days today)

Practical approach:

1. Run 2 sweeps nightly:

* 30m/5m (primary mode)
* 1h/5m (fallback mode that avoids restart complexity if you prefer)

2. Don't do 500k trials nightly
   Your 500k sweeps are great for occasional deep dives, but in a daily pipeline you want "good enough candidates fast." You can do something like 50k–150k trials per combo nightly, then periodically do a 500k "refresh" on weekends.

3. Generate not just rank #1, generate a shortlist
   For each sweep output, produce:

* Top 10 by DD
* Top 10 by "balanced"
* (Optionally) top 10 by PF or Sharpe, but only if you enforce a min-trades constraint

Why? Because your live choice should be based on out-of-sample stability, not in-sample rank.

You already have the tooling for this (`generate_config.py`). You'd just call it in a loop.

---

C) Robust validation loop (nightly)

This is the critical missing layer between "backtest winners" and "something you can trade."

Your current "apple-to-apple 12 days, force 3m entry/exit" replay is a good comparability tool, but it's not a robustness test by itself because:

* it's still in-sample relative to the sweep window,
* 12 days is too short to trust Sharpe,
* and you're doing heavy multiple testing (500k trials).

So the validation loop needs to introduce "friction" and "out-of-sample pressure" in a way you can automate now, even with short data.

Here's a validation protocol that fits your constraints:

1. Multi-split walk-forward on the short window
   Even with 19 days, you can do a few splits.

Example for a 19-day 5m dataset:

* Split 1: train days 1–12, test days 13–19
* Split 2: train days 4–15, test days 16–19
* Split 3: train days 1–9,  test days 10–19  (more aggressive OOS)

Mechanically, you need the ability to replay on specific subranges. If your CLI doesn't support explicit start/end yet, add it. This one feature pays for itself immediately.

2. Slippage/fee stress test
   Right now you assume 10 bps slippage. In real alts/perps, your realized slippage can be much worse during spikes.

Nightly, replay each candidate at:

* 10 bps (baseline)
* 20 bps (realistic stress)
* 30 bps (bad conditions)

Reject configs that flip sign or blow up DD under modest friction.

If your engine only supports slippage via config, generate variants automatically (same config, different `slippage_bps`).

3. Concentration checks
   A config that makes all its money on 1–2 symbols will "feel great" until it dies.

For each candidate, compute:

* % of PnL from top 1 symbol
* % of PnL from top 5 symbols
* long vs short contribution
* number of distinct symbols traded

Reject candidates that are too concentrated.

4. Stability score (one number to rank candidates)
   You need a single scalar score to pick "best for live." A simple one you can automate is:

score = median(OOS_daily_return)
− 2.0 * max(OOS_drawdown)
− 0.5 * (PnL_drop_when_slippage_20bps)
− penalty_if_trades_too_low

This does three important things:

* rewards out-of-sample performance,
* punishes tail risk (drawdown),
* punishes fragility to friction.

The exact weights don't matter as much as having a consistent rule and logging outcomes.

---

D) Deployment loop (controlled + gated)

Your deployment should not be "deploy the #1 backtest config." It should be:

1. Deploy to paper first (always)

* Pick top 1–3 validated candidates.
* Run them paper for a fixed minimum sample (e.g., 1 trading day or N trades).
* Log live-style metrics: fills, slippage, funding, latency, rejection rate.

2. Promote to live with a ramp
   Because your bankroll is small and you're using leverage, your biggest enemy is variance + a few bad fills.

A simple ramp rule:

* Start at 25% of intended size for the first day.
* If no kill-switch triggers and slippage is within bounds, step up.
* If something looks off, step down or pause.

3. Version everything
   Every deployment should write:

* config hash / git commit
* sweep file ref
* validation report ref
* start timestamp
* stop timestamp + reason (rotated, killed, decayed)

This turns your trading into an engineering process instead of a feeling.

---

E) Live monitoring + kill switches (continuous)

This is where most "profitable backtests" go to die. You want your bot to stop itself before it ruins you.

Minimum viable kill switches you can automate today:

1. Equity drawdown kill
   If peak-to-valley drawdown exceeds X%, stop trading and go to "safe mode" (or flat).
   Pick X so you can survive, not so you can "maximize returns."

2. Daily loss limit
   If today's realized PnL < −Y%, stop trading until next UTC day.

3. Performance degradation trigger
   Compute rolling live PF / Sharpe / win rate over last N trades or last 24h:

* If PF < 1.0 after at least (say) 30 trades, pause.
* If slippage exceeds your stress-tested expectations, pause.

4. Regime gate (you already have breadth)
   Since your strategy is momentum-flavored, don't force it to trade mean-reverting chop.
   Add a "do not trade" gate if breadth/trend metrics indicate chop (whatever definition your code supports).

Even a crude regime gate often improves survivability more than another 500k sweep.

---

What to do with your current best configs (practical plan)

Given your report, a very pragmatic "three-mode" system is:

Mode 1 (Primary): 30m/5m DD

* Use when market is trending / breadth supportive.
* This is your best current performer on the comparable 12-day test and profitable on its 19-day native window.

Mode 2 (Fallback): 1h/5m DD

* Use when you want less operational complexity (no main interval restart) or if 30m mode degrades.
* Also profitable on the 19-day window.

Mode 3 (Safety / Recovery): 1h/15m DD (or flat)

* Use when volatility gets weird or chop increases and you want minimal DD.
* Not because it "earns the most," but because it helps you not die.

Then automate switching rules:

* If Mode 1 violates kill-switch thresholds → switch to Mode 2 or Mode 3.
* If Mode 2 also violates → go Mode 3 or flat.
* When conditions recover and your nightly validation says Mode 1 is healthy again → return.

This turns your single strategy into a regime-aware system without writing an entirely new alpha.

---

Two important "understanding" points that will save you months

1. Your 12-day +239% result is not a target; it's a symptom of high variance and multiple testing.
   Over short windows, returns can look insane. The job of the workflow is not to chase that number; it's to make sure your live process doesn't blow up when the inevitable bad streak arrives.

2. Right now, your limiting factor is not TPE or GPU speed. It's out-of-sample evidence.
   With 12–19 days of high-resolution data, you can't honestly claim robustness. So either:

* accept the "short-lived edge + rapid rotation" business model, or
* invest in building longer 3m/5m history so you can validate properly.

That's the fork in the road.

---

A concrete automation blueprint (how it looks as a daily pipeline)

This is what I would automate first, using your existing CLI pieces:

Every night (UTC):

1. Update funding DB (`fetch_funding_rates.py`) and confirm candle DB freshness.
2. Run GPU sweeps:

   * 30m/5m with (say) 100k–200k trials
   * 1h/5m with (say) 100k–200k trials
3. Generate top candidates:

   * top 10 by DD
   * top 10 by balanced
4. Run CPU validation suite for each candidate:

   * native interval replay (5m/5m) on full available range
   * 2–3 walk-forward splits (if you add time range control)
   * slippage stress (10/20/30 bps)
   * concentration metrics
5. Pick top 1–3 configs by your stability score.
6. Deploy best config to paper for the next session (or keep current live if it's still healthy).
7. If live is enabled, only promote a config that passed validation + paper gates.

During the day:

* Monitor live stats and enforce kill switches.
* If killed, immediately fall back to safety mode (or flat), and wait for next nightly cycle to propose replacements.

This is actionable, repeatable, and automatable with what you already built.

---

One last thing: there are inconsistencies in the parameter snippet you included

In your "Top Performer: 30m/5m DD" YAML snippet, values like `ema_fast_window: 5`, `allocation_pct: 0.109937`, and `leverage: 4.574699` don't match the sweep ranges you listed earlier (e.g., ema_fast_window was shown as [9–13], allocation_pct [0.17–0.30], leverage [3.0–4.3]). That doesn't change the high-level conclusion, but it does mean: treat `/tmp/config_30m5m_best_dd.yaml` as the source of truth and don't rely on the snippet when deploying.

---

If you want the shortest path to "something that can actually run," do this:

* Run 30m/5m DD in paper immediately, but add strict kill-switches and a daily validation pipeline.
* In parallel, modify your data storage so 3m/5m history grows beyond 12–19 days. That one change massively improves your ability to validate and reduces the need for frantic parameter rotation.

If you want, I can also outline exactly what to log (fields/events) so you can later answer the only question that matters: "When this thing made or lost money live, why?"
