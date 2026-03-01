#!/usr/bin/env bash
set -euo pipefail

# 17-phase 144v sweep runner (grid).
#
# Default scale (from manifest):
# - 17 phases
# - ~100k combos per interval (targeted)
# - Intervals: 3m, 5m, 15m, 30m

cd "$(dirname "${BASH_SOURCE[0]}")/.."

BT="./target/release/mei-backtester"
PHASE_DIR="sweeps/full_144v_17phase"
MANIFEST="${PHASE_DIR}/manifest.yaml"
CONFIG="../config/strategy_overrides.yaml"
OUTDIR="sweep_results/phase144v"
INTERVALS="3m 5m 15m 30m"
USE_GPU=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --intervals) INTERVALS="$2"; shift 2 ;;
        --outdir) OUTDIR="$2"; shift 2 ;;
        --cpu) USE_GPU=0; shift ;;
        --config) CONFIG="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [[ ! -f "$BT" ]]; then
    echo "ERROR: Backtester not found at $BT"
    echo "Build with: cargo build --release -p bt-cli --features gpu"
    exit 1
fi
if [[ ! -f "$MANIFEST" ]]; then
    echo "ERROR: Manifest not found at $MANIFEST"
    echo "Generate with: python3 sweeps/generate_17phase_144v.py"
    exit 1
fi
if [[ ! -f "$CONFIG" ]]; then
    echo "ERROR: Strategy config not found at $CONFIG"
    exit 1
fi

if [[ "$USE_GPU" -eq 1 ]]; then
    export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:/usr/lib/wsl/lib"
fi

PHASE_INFO_JSON="$(python3 - "$MANIFEST" <<'PY'
import json, sys, yaml
m = yaml.safe_load(open(sys.argv[1], "r", encoding="utf-8").read()) or {}
ph = m.get("phases", [])
out = []
for p in ph:
    out.append({
        "id": str(p.get("id", "")),
        "file": str(p.get("file", "")),
        "combo": int(p.get("combo", 0)),
    })
print(json.dumps(out))
PY
)"

TOTAL_COMBOS="$(python3 - "$MANIFEST" <<'PY'
import sys, yaml
m = yaml.safe_load(open(sys.argv[1], "r", encoding="utf-8").read()) or {}
print(int(m.get("total_combo", 0)))
PY
)"

mkdir -p "$OUTDIR"

echo "=============================================================="
echo " 17-phase 144v sweep"
echo " combos per interval: ${TOTAL_COMBOS}"
echo " intervals: ${INTERVALS}"
echo " mode: $( [[ "$USE_GPU" -eq 1 ]] && echo GPU || echo CPU )"
echo "=============================================================="

START_TIME=$(date +%s)
TOTAL_RUNS=0

for interval in $INTERVALS; do
    echo ""
    echo "Interval: ${interval}"
    echo "--------------------------------------------------------------"
    while IFS=$'\t' read -r phase_id phase_file phase_combo; do
        spec_path="${PHASE_DIR}/${phase_file}"
        out_jsonl="${OUTDIR}/${phase_id}_${interval}.jsonl"
        if [[ ! -f "$spec_path" ]]; then
            echo "[SKIP] ${phase_id}: missing ${spec_path}"
            continue
        fi

        echo -n "[RUN] ${phase_id} (${phase_combo} combos) ... "
        phase_start=$(date +%s)

        if [[ "$USE_GPU" -eq 1 ]]; then
            "$BT" sweep \
                --config "$CONFIG" \
                --sweep-spec "$spec_path" \
                --interval "$interval" \
                --gpu \
                --output "$out_jsonl" \
                --top-n 0 >/dev/null 2>&1
        else
            "$BT" sweep \
                --config "$CONFIG" \
                --sweep-spec "$spec_path" \
                --interval "$interval" \
                --output "$out_jsonl" \
                --top-n 0 >/dev/null 2>&1
        fi

        phase_end=$(date +%s)
        elapsed=$((phase_end - phase_start))
        lines=$(wc -l < "$out_jsonl" 2>/dev/null || echo 0)
        echo "${lines} done in ${elapsed}s"
        TOTAL_RUNS=$((TOTAL_RUNS + lines))
    done < <(
        python3 - "$PHASE_INFO_JSON" <<'PY'
import json, sys
for p in json.loads(sys.argv[1]):
    print(f"{p['id']}\t{p['file']}\t{p['combo']}")
PY
    )
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "=============================================================="
echo "Complete"
echo " total runs: ${TOTAL_RUNS}"
echo " elapsed: ${ELAPSED}s"
echo " output: ${OUTDIR}"
echo "=============================================================="
