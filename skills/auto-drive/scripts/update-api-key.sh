#!/usr/bin/env bash
# Update the Auto-Drive API key without re-running full setup
# Usage: ./scripts/update-api-key.sh
# Env: AUTO_DRIVE_API_KEY may be set to skip the prompt (non-interactive use)

set -euo pipefail

# shellcheck source=_lib.sh
source "$(dirname "$0")/_lib.sh"

ad_warn_git_bash
ad_require_tools curl jq

# Accept key from argument, interactive prompt, or env var (CI only).
# When stdin is a terminal we always prompt so the user isn't silently
# handed back the old key that is already exported in their shell.
if [[ -n "${1:-}" ]]; then
  API_KEY="$1"
elif [[ -t 0 ]]; then
  read -rp "New Auto-Drive API key: " API_KEY
elif [[ -n "${AUTO_DRIVE_API_KEY:-}" ]]; then
  API_KEY="$AUTO_DRIVE_API_KEY"
else
  echo -e "${RED}Error: No API key provided (non-interactive and AUTO_DRIVE_API_KEY is unset).${NC}" >&2
  exit 1
fi
API_KEY="${API_KEY//[[:space:]]/}"

if [[ -z "$API_KEY" ]]; then
  echo -e "${RED}Error: No API key provided.${NC}" >&2
  exit 1
fi

autodrive_verify_key "$API_KEY"
autodrive_save_key "$API_KEY"

echo ""
echo "API key updated. Restart the OpenClaw gateway to apply."
