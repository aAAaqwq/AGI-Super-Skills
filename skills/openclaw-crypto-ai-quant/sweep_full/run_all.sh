#!/usr/bin/env bash
set -euo pipefail

# Full parameter sweep: 17 phases × 4 entry/exit intervals
# Total: ~15,161 combos × 4 intervals = ~60,644 simulation runs

BT="./backtester/target/release/mei-backtester"
OUTDIR="sweep_full/results"
mkdir -p "$OUTDIR"

PHASES=(
  "p01_core_trade:3780"
  "p02_entry_thresholds:480"
  "p03_entry_toggles:256"
  "p04_execution_gates:5120"
  "p05_trailing_exits:900"
  "p06_smart_exits:144"
  "p07_market_regime:324"
  "p08_indicator_windows:972"
  "p09_pullback_drift:768"
  "p10_dynamic_sizing:1296"
  "p11_pyramiding:162"
  "p12_low_conf_exits:144"
  "p13_rsi_exit_extended:243"
  "p14_stoch_rsi:96"
  "p15_momentum_tp:144"
  "p16_vol_sizing:108"
  "p17_entry_confidence:144"
)

INTERVALS=("3m" "5m" "15m" "30m")

TOTAL_COMBOS=0
TOTAL_RUNS=0
START_TIME=$(date +%s)

echo "=============================================="
echo " Full Parameter Sweep"
echo " 17 phases × 4 intervals"
echo " Started: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=============================================="
echo ""

for interval in "${INTERVALS[@]}"; do
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo " Entry/Exit interval: $interval"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  for phase_info in "${PHASES[@]}"; do
    phase="${phase_info%%:*}"
    expected="${phase_info##*:}"
    spec="sweep_full/${phase}.yaml"
    outfile="${OUTDIR}/${phase}_${interval}.jsonl"

    echo -n "  [${phase}] ${expected} combos @ ${interval} ... "
    phase_start=$(date +%s)

    $BT sweep \
      --sweep-spec "$spec" \
      --interval 1h \
      --entry-interval "$interval" \
      --exit-interval "$interval" \
      --output "$outfile" \
      --top-n 0 \
      2>/dev/null

    phase_end=$(date +%s)
    phase_secs=$((phase_end - phase_start))
    combos=$(wc -l < "$outfile")
    rate=$(echo "scale=1; $combos / ($phase_secs + 1)" | bc 2>/dev/null || echo "?")
    echo "${combos} done in ${phase_secs}s (${rate}/s)"

    TOTAL_COMBOS=$((TOTAL_COMBOS + combos))
    TOTAL_RUNS=$((TOTAL_RUNS + combos))
  done
  echo ""
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo "=============================================="
echo " Sweep complete!"
echo " Total runs:   $TOTAL_RUNS"
echo " Elapsed:      ${ELAPSED}s"
echo "=============================================="
echo ""

# Merge all JSONL files into a single CSV
echo "Generating combined CSV..."

python3 -u - "$OUTDIR" <<'PYEOF'
import json, csv, sys, os, glob

outdir = sys.argv[1]
files = sorted(glob.glob(os.path.join(outdir, "*.jsonl")))

rows = []
for fpath in files:
    # Extract phase and interval from filename: p01_core_trade_3m.jsonl
    fname = os.path.basename(fpath).replace(".jsonl", "")
    parts = fname.rsplit("_", 1)
    if len(parts) == 2:
        phase, interval = parts
    else:
        phase, interval = fname, "?"

    with open(fpath) as f:
        for line_no, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue

            row = {
                "phase": phase,
                "interval": interval,
                "config_id": r.get("config_id", ""),
                "total_pnl": r.get("total_pnl", 0),
                "total_trades": r.get("total_trades", 0),
                "win_rate": round(r.get("win_rate", 0) * 100, 2),
                "profit_factor": r.get("profit_factor", 0),
                "sharpe_ratio": round(r.get("sharpe_ratio", 0), 4),
                "max_drawdown_pct": round(r.get("max_drawdown_pct", 0) * 100, 2),
                "max_drawdown_usd": round(r.get("max_drawdown_usd", 0), 2),
                "avg_win": round(r.get("avg_win", 0), 2),
                "avg_loss": round(r.get("avg_loss", 0), 2),
                "total_fees": round(r.get("total_fees", 0), 2),
                "total_wins": r.get("total_wins", 0),
                "total_losses": r.get("total_losses", 0),
                "final_balance": round(r.get("final_balance", 0), 2),
            }

            # Extract overrides from the report if present
            overrides = r.get("overrides", {})
            if isinstance(overrides, dict):
                for k, v in overrides.items():
                    row[k] = v

            rows.append(row)

if not rows:
    print("No results found!", file=sys.stderr)
    sys.exit(1)

# Collect all column names
base_cols = ["phase", "interval", "config_id", "total_pnl", "total_trades",
             "win_rate", "profit_factor", "sharpe_ratio", "max_drawdown_pct",
             "max_drawdown_usd", "avg_win", "avg_loss", "total_fees",
             "total_wins", "total_losses", "final_balance"]
override_cols = sorted(set(k for r in rows for k in r if k not in base_cols))
all_cols = base_cols + override_cols

csv_path = os.path.join(os.path.dirname(outdir), "sweep_full_results.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=all_cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

print(f"CSV written: {csv_path} ({len(rows)} rows, {len(all_cols)} columns)")
PYEOF

echo "Done!"
