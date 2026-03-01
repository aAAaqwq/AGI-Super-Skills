#!/usr/bin/env bash
# Setup Autonomys Auto-Drive — interactive API key configuration
# Usage: ./scripts/setup-auto-drive.sh
# Opens explorer.ai3.storage in your browser, prompts for the API key,
# writes it to ~/.openclaw/openclaw.json (skills.entries.auto-drive.env)
# and ~/.openclaw/.env, then verifies the connection.

set -euo pipefail

# shellcheck source=_lib.sh
source "$(dirname "$0")/_lib.sh"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Autonomys Auto-Drive — Setup            ║"
echo "╚══════════════════════════════════════════╝"
echo ""

ad_warn_git_bash
ad_require_tools curl jq
echo -e "${GREEN}✓ Prerequisites OK (curl, jq)${NC}"
echo ""

# Open browser to API key creation page
DASHBOARD_URL="https://explorer.ai3.storage/mainnet/drive/developers"
echo "Opening $DASHBOARD_URL in your browser..."
echo ""
echo "  → If prompted, sign in with Google, GitHub, or Discord"
echo "     (AI agents: you cannot complete OAuth yourself —"
echo "      ask the user to sign in, then take over)"
echo "  → Click 'Create API Key' and paste the key below"
echo ""
if command -v xdg-open &>/dev/null; then
  xdg-open "$DASHBOARD_URL" 2>/dev/null &
elif command -v open &>/dev/null; then
  open "$DASHBOARD_URL" 2>/dev/null &
elif [[ -n "${WSL_DISTRO_NAME:-}" ]] || grep -qi microsoft /proc/version 2>/dev/null; then
  cmd.exe /c start "" "$DASHBOARD_URL" 2>/dev/null &
else
  echo -e "${YELLOW}Could not open browser automatically — visit: $DASHBOARD_URL${NC}"
fi

read -rp "Paste your API key here: " API_KEY
API_KEY="${API_KEY//[[:space:]]/}"

if [[ -z "$API_KEY" ]]; then
  echo -e "${RED}Error: No API key provided.${NC}" >&2
  exit 1
fi

echo ""
autodrive_verify_key "$API_KEY"
autodrive_save_key "$API_KEY"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Setup complete!                         ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Restart OpenClaw gateway to pick up the new config"
echo "  2. Try: scripts/autodrive-upload.sh /path/to/any/file"
echo "  3. Or run: scripts/verify-setup.sh"
echo ""
echo "Or ask your agent: 'Save a memory that Auto-Drive is now configured'"
echo ""
