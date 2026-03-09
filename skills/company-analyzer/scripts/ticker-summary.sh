#!/bin/bash
#
# ticker-summary.sh - Audit report for Ticker Analysis costs and efficiency
#

# 1. Path Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
COST_LOG="$SKILL_DIR/.cache/costs.log"

# Check if log exists
if [ ! -f "$COST_LOG" ]; then
    echo "❌ No cost log found at $COST_LOG"
    exit 1
fi

echo "========================================================="
echo "📊 COMPANY ANALYZER: TICKER COST SUMMARY"
echo "========================================================="
printf "%-10s | %-10s | %-12s | %-8s\n" "TICKER" "RUNS" "TOTAL TOKENS" "COST ($)"
echo "---------------------------------------------------------"

# 2. Process Log Data
# Log format: timestamp | ticker | framework | model | 123i/456o | $cost
# With -F' | ' (space OR space in awk regex) we split on space: $3=ticker $5=framework $9=tokens $11=cost
awk -F' | ' '
{
    ticker = $3;
    split($9, t, "/");
    in_t = out_t = 0;
    sub(/i$/, "", t[1]); in_t = t[1] + 0;
    sub(/o$/, "", t[2]); out_t = t[2] + 0;
    cost_str = $11;
    gsub(/\$/, "", cost_str);
    counts[ticker]++;
    tokens[ticker] += (in_t + out_t);
    costs[ticker] += cost_str + 0;
}
END {
    for (x in counts) {
        printf "%-10s | %-10d | %-12d | $%-8.4f\n", x, counts[x], tokens[x], costs[x]
    }
}' "$COST_LOG" | sort -t'|' -k4 -rn

echo "---------------------------------------------------------"

# 3. Framework Efficiency Audit
echo ""
echo "🔍 Framework Efficiency (Average Cost per Call)"
echo "---------------------------------------------------------"
awk -F' | ' '
{
    fw = $5;
    cost_str = $11;
    gsub(/\$/, "", cost_str);
    fw_counts[fw]++;
    fw_costs[fw] += cost_str + 0;
}
END {
    for (f in fw_counts) {
        avg = fw_costs[f] / fw_counts[f];
        printf "%-20s | Avg Cost: $%-8.6f | Runs: %d\n", f, avg, fw_counts[f]
    }
}' "$COST_LOG" | sort -t'|' -k4 -rn

echo "========================================================="