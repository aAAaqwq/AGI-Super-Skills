#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# Full TPE Sweep Runner — 144v profile (broad strategy coverage)
# ═══════════════════════════════════════════════════════════════════════════
#
# Runs TPE Bayesian optimisation across the default 144v profile for each
# main candle interval. Auto-scope ensures apple-to-apple within each run.
#
# GPU sweep does NOT support sub-bar entry/exit intervals (main only).
# Each interval uses its own candle DB with different data coverage:
#   1m=3.5d, 3m=10d, 5m=17d, 15m=52d, 30m=104d, 1h=208d
#
# Usage:
#   ./run_full_sweep.sh                    # all intervals, 500K trials
#   ./run_full_sweep.sh --trials 100000    # quick test
#   ./run_full_sweep.sh --intervals "15m 1h"  # specific intervals only
#
# Runtime varies by axis count, batch size, and host GPU throughput.
#
# Kill if over 10 minutes: built-in timeout per run.
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Run from the backtester/ directory (one level up from sweeps/).
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# ── Config ──────────────────────────────────────────────────────────────
TRIALS=500000
BATCH=4096
SEED=42
SWEEP_SPEC="sweeps/full_144v.yaml"
CONFIG="../config/strategy_overrides.yaml"
BACKTESTER="./target/release/mei-backtester"
OUTPUT_DIR="sweep_results"
INTERVALS="3m 5m 15m 30m 1h"      # skip 1m (only 3.5d data, marginal)
TIMEOUT_PER_RUN=120                 # seconds per interval run (kill if exceeded)
INITIAL_BALANCE=10000.0

# ── Parse CLI args ──────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --trials)     TRIALS="$2"; shift 2 ;;
        --batch)      BATCH="$2"; shift 2 ;;
        --seed)       SEED="$2"; shift 2 ;;
        --intervals)  INTERVALS="$2"; shift 2 ;;
        --timeout)    TIMEOUT_PER_RUN="$2"; shift 2 ;;
        --spec)       SWEEP_SPEC="$2"; shift 2 ;;
        --balance)    INITIAL_BALANCE="$2"; shift 2 ;;
        --include-1m) INTERVALS="1m $INTERVALS"; shift ;;
        *)            echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# ── Validate ────────────────────────────────────────────────────────────
if [[ ! -f "$BACKTESTER" ]]; then
    echo "ERROR: Backtester not found at $BACKTESTER"
    echo "Build with: cargo build --release -p bt-cli --features gpu"
    exit 1
fi

if [[ ! -f "$SWEEP_SPEC" ]]; then
    echo "ERROR: Sweep spec not found at $SWEEP_SPEC"
    exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
    echo "ERROR: Strategy config not found at $CONFIG"
    exit 1
fi

# WSL2 CUDA library path
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:/usr/lib/wsl/lib"

mkdir -p "$OUTPUT_DIR"

AXIS_COUNT="$(python3 - "$SWEEP_SPEC" <<'PY'
import sys, yaml
try:
    spec = yaml.safe_load(open(sys.argv[1], "r", encoding="utf-8").read()) or {}
    print(len(spec.get("axes", [])))
except Exception:
    print("?")
PY
)"

# ── Data coverage info ──────────────────────────────────────────────────
declare -A INTERVAL_DAYS=(
    [1m]="3.5"
    [3m]="10"
    [5m]="17"
    [15m]="52"
    [30m]="104"
    [1h]="208"
)

# ── Run ─────────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════════"
echo "Full TPE Sweep: ${AXIS_COUNT} axes (${SWEEP_SPEC}) × ${TRIALS} trials × batch=${BATCH}"
echo "Intervals: ${INTERVALS}"
echo "Timeout per run: ${TIMEOUT_PER_RUN}s"
echo "═══════════════════════════════════════════════════════════════"
echo ""

TOTAL_START=$(date +%s)
RUN_COUNT=0
FAIL_COUNT=0

for IV in $INTERVALS; do
    DB="candles_dbs/candles_${IV}.db"
    if [[ ! -f "$DB" ]]; then
        echo "[SKIP] $IV — DB not found: $DB"
        continue
    fi

    OUTFILE="${OUTPUT_DIR}/tpe_${IV}_${TRIALS}t.jsonl"
    DAYS="${INTERVAL_DAYS[$IV]:-?}"

    echo "──────────────────────────────────────────────────────────"
    echo "[RUN] interval=${IV} (${DAYS}d data), trials=${TRIALS}, batch=${BATCH}"
    echo "  DB: ${DB}"
    echo "  Output: ${OUTFILE}"

    RUN_START=$(date +%s)

    if timeout "${TIMEOUT_PER_RUN}" \
        "$BACKTESTER" sweep \
            --gpu \
            --allow-unsafe-gpu-sweep \
            --tpe \
            --tpe-trials "$TRIALS" \
            --tpe-batch "$BATCH" \
            --tpe-seed "$SEED" \
            --interval "$IV" \
            --config "$CONFIG" \
            --sweep-spec "$SWEEP_SPEC" \
            --output "$OUTFILE" \
            --initial-balance "$INITIAL_BALANCE" \
            --top-n 1000 \
        2>&1; then
        RUN_END=$(date +%s)
        ELAPSED=$((RUN_END - RUN_START))
        LINES=$(wc -l < "$OUTFILE" 2>/dev/null || echo 0)
        echo "[DONE] ${IV}: ${ELAPSED}s, ${LINES} results written"
        RUN_COUNT=$((RUN_COUNT + 1))
    else
        EXIT_CODE=$?
        RUN_END=$(date +%s)
        ELAPSED=$((RUN_END - RUN_START))
        if [[ $EXIT_CODE -eq 124 ]]; then
            echo "[TIMEOUT] ${IV}: killed after ${TIMEOUT_PER_RUN}s"
        else
            echo "[FAIL] ${IV}: exit code ${EXIT_CODE} after ${ELAPSED}s"
        fi
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    echo ""
done

TOTAL_END=$(date +%s)
TOTAL_ELAPSED=$((TOTAL_END - TOTAL_START))

echo "═══════════════════════════════════════════════════════════════"
echo "COMPLETE: ${RUN_COUNT} OK, ${FAIL_COUNT} failed, ${TOTAL_ELAPSED}s total"
echo "Results in: ${OUTPUT_DIR}/"
echo "═══════════════════════════════════════════════════════════════"

# ── Summary: top result per interval ────────────────────────────────────
echo ""
echo "Top result per interval:"
for IV in $INTERVALS; do
    OUTFILE="${OUTPUT_DIR}/tpe_${IV}_${TRIALS}t.jsonl"
    if [[ -f "$OUTFILE" ]]; then
        # First line = best (already sorted by PnL desc)
        HEAD=$(head -1 "$OUTFILE" 2>/dev/null || echo "{}")
        PNL=$(echo "$HEAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'PnL=\${d[\"total_pnl\"]:.2f}, trades={d[\"total_trades\"]}, WR={d[\"win_rate\"]*100:.1f}%, PF={d[\"profit_factor\"]:.2f}')" 2>/dev/null || echo "parse error")
        echo "  ${IV}: ${PNL}"
    fi
done
