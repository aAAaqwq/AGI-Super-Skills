#!/usr/bin/env bash
# rotate-key.sh — Rotate a single API key end-to-end
# Usage: bash rotate-key.sh <pass-path> [new-key-value]
# Example: bash rotate-key.sh api/zai sk-newkeyhere
set -euo pipefail

PASS_PATH="${1:-}"
NEW_KEY="${2:-}"

if [[ -z "$PASS_PATH" ]]; then
    echo "Usage: bash rotate-key.sh <pass-path> [new-key-value]"
    echo "Example: bash rotate-key.sh api/zai sk-newkey123"
    echo ""
    echo "Available pass entries:"
    pass ls api/ 2>/dev/null | head -40
    exit 1
fi

echo "🔄 Rotating key: $PASS_PATH"

# Step 1: Update pass
if [[ -n "$NEW_KEY" ]]; then
    echo "$NEW_KEY" | pass insert -f "$PASS_PATH"
    echo "  ✅ pass updated"
else
    echo "  Enter new key value:"
    pass insert -f "$PASS_PATH"
fi

# Step 2: Rebuild .env
echo ""
echo "📝 Rebuilding .env..."
bash "$(dirname "$0")/rebuild-env.sh"

# Step 3: Restart gateway
echo ""
echo "🔄 Restarting gateway..."
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway
sleep 3

# Step 4: Verify
echo ""
bash "$(dirname "$0")/verify-keys.sh"

echo ""
echo "✅ Key rotation complete for: $PASS_PATH"
