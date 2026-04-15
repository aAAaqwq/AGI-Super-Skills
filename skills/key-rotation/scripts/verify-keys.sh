#!/usr/bin/env bash
# verify-keys.sh — Verify all env vars are loaded in the running gateway
set -euo pipefail

echo "🔍 Verifying OpenClaw Gateway API keys..."

# Get gateway PID
GW_PID=$(pgrep -f "openclaw-gateway" || pgrep -f "openclaw.*gateway" || true)

if [[ -z "$GW_PID" ]]; then
    echo "❌ Gateway not running!"
    exit 1
fi

echo "Gateway PID: $GW_PID"
echo ""

# Read .env var names
ENV_FILE="$HOME/.openclaw/.env"
PASS=0
FAIL=0
EMPTY=0

while IFS= read -r line; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    VAR_NAME="${line%%=*}"
    
    # Check if var is in process environment
    if grep -qz "^${VAR_NAME}=" /proc/$GW_PID/environ 2>/dev/null; then
        # Check it's not empty
        VAL=$(tr '\0' '\n' < /proc/$GW_PID/environ | grep "^${VAR_NAME}=" | head -1 | cut -d= -f2-)
        if [[ -n "$VAL" && "$VAL" != "env:"* ]]; then
            echo "  ✅ $VAR_NAME = ${VAL:0:6}***"
            ((PASS++))
        else
            echo "  ⚠️  $VAR_NAME = (empty or unresolved)"
            ((EMPTY++))
        fi
    else
        echo "  ❌ $VAR_NAME = NOT IN PROCESS ENV"
        ((FAIL++))
    fi
done < "$ENV_FILE"

echo ""
echo "Results: $PASS loaded, $FAIL missing, $EMPTY empty"

if [[ $FAIL -gt 0 || $EMPTY -gt 0 ]]; then
    echo ""
    echo "💡 Fix: systemctl --user daemon-reload && systemctl --user restart openclaw-gateway"
    exit 1
else
    echo "✅ All keys verified!"
fi
