#!/usr/bin/env bash
# Shared helpers for Auto-Drive scripts.  Source this file; do not execute it.
# Usage: source "$(dirname "$0")/_lib.sh"

# -- Constants ----------------------------------------------------------------

AD_API_BASE="https://mainnet.auto-drive.autonomys.xyz/api"
AD_DOWNLOAD_API="https://public.auto-drive.autonomys.xyz/api"
AD_OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"
AD_ENV_FILE="$AD_OPENCLAW_DIR/.env"
AD_CONFIG_FILE="$AD_OPENCLAW_DIR/openclaw.json"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# -- Platform / dependency helpers -------------------------------------------

# Print a platform-appropriate install hint for one or more packages.
# Usage: ad_install_hint <pkg> [pkg ...]
ad_install_hint() {
  case "$(uname -s 2>/dev/null)" in
    Linux*)               echo "  Install: sudo apt install $*" >&2 ;;
    Darwin*)              echo "  Install: brew install $*" >&2 ;;
    MINGW*|MSYS*|CYGWIN*) echo "  Install: winget install $* OR choco install $*" >&2 ;;
    *)                    echo "  Install: $*" >&2 ;;
  esac
}

# Warn Git Bash / Windows users about potential compatibility issues.
ad_warn_git_bash() {
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*)
      echo "Note: Running in Git Bash. For full compatibility, consider using WSL." >&2
      echo "WSL setup: https://learn.microsoft.com/en-us/windows/wsl/install" >&2
      ;;
  esac
}

# Check that all listed commands exist; exit 1 with install hint if any are missing.
# Usage: ad_require_tools curl jq
ad_require_tools() {
  local _missing=()
  local _cmd
  for _cmd in "$@"; do
    command -v "$_cmd" &>/dev/null || _missing+=("$_cmd")
  done
  if [[ ${#_missing[@]} -gt 0 ]]; then
    echo -e "${RED}Error: Missing required tools: ${_missing[*]}${NC}" >&2
    ad_install_hint "${_missing[@]}"
    exit 1
  fi
}

# -- Validation helpers ------------------------------------------------------

# Autonomys CID format: base32-encoded, starting with "baf".
AD_CID_RE='^baf[a-z2-7]{50,100}$'

# Return 0 if the argument looks like a valid Autonomys CID, 1 otherwise.
# Usage: ad_valid_cid "$CID"
ad_valid_cid() { [[ "${1:-}" =~ $AD_CID_RE ]]; }

# -- Functions ----------------------------------------------------------------

# Verify an API key against the Auto-Drive accounts endpoint.
# On success, sets AD_VERIFY_BODY with the JSON response.
# On failure, prints an error to stderr and returns 1.
# Usage: autodrive_verify_key "$API_KEY"
autodrive_verify_key() {
  local key="$1"
  echo "Verifying API key..."
  local response http_code body
  response=$(curl -sS -w "\n%{http_code}" "$AD_API_BASE/accounts/@me" \
    -H "Authorization: Bearer $key" \
    -H "X-Auth-Provider: apikey")
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" -lt 200 || "$http_code" -ge 300 ]]; then
    echo -e "${RED}Error: API key verification failed (HTTP $http_code).${NC}" >&2
    echo "$body" >&2
    return 1
  fi
  AD_VERIFY_BODY="$body"
  echo -e "${GREEN}✓ API key verified${NC}"
}

# Save an API key to openclaw.json and .env.
# Creates $AD_OPENCLAW_DIR if it doesn't exist.
# Temp files are cleaned up on exit via trap.
# Usage: autodrive_save_key "$API_KEY"
autodrive_save_key() {
  local key="$1"

  mkdir -p "$AD_OPENCLAW_DIR"
  chmod 700 "$AD_OPENCLAW_DIR"

  # Collect temp files for cleanup
  _AD_TMPS=()
  trap 'rm -f "${_AD_TMPS[@]}"' EXIT

  # --- openclaw.json ---------------------------------------------------------
  # Write to .apiKey (not .env.AUTO_DRIVE_API_KEY) — the skill declares
  # primaryEnv: AUTO_DRIVE_API_KEY, so the gateway maps .apiKey to that
  # env var automatically.  This matches the documented config path:
  # skills.entries.auto-drive.apiKey
  if [[ ! -f "$AD_CONFIG_FILE" ]]; then
    local newtmp
    newtmp=$(mktemp)
    _AD_TMPS+=("$newtmp")
    jq -n --arg key "$key" \
      '{"skills": {"entries": {"auto-drive": {"enabled": true, "apiKey": $key}}}}' \
      > "$newtmp" && mv "$newtmp" "$AD_CONFIG_FILE"
    chmod 600 "$AD_CONFIG_FILE"
  else
    local jsontmp
    jsontmp=$(mktemp)
    _AD_TMPS+=("$jsontmp")
    jq --arg key "$key" \
      '.skills //= {} | .skills.entries //= {} | .skills.entries["auto-drive"] //= {} | .skills.entries["auto-drive"].apiKey = $key | .skills.entries["auto-drive"].enabled = true' \
      "$AD_CONFIG_FILE" > "$jsontmp" && mv "$jsontmp" "$AD_CONFIG_FILE"
    chmod 600 "$AD_CONFIG_FILE"
  fi
  echo -e "${GREEN}✓ Saved to $AD_CONFIG_FILE${NC}"

  # --- .env ------------------------------------------------------------------
  # Remove any existing AUTO_DRIVE_API_KEY lines first to prevent duplicates,
  # then append exactly one entry.
  if [[ -f "$AD_ENV_FILE" ]]; then
    local sedtmp
    sedtmp=$(mktemp)
    _AD_TMPS+=("$sedtmp")
    sed '/^AUTO_DRIVE_API_KEY=/d' "$AD_ENV_FILE" > "$sedtmp" && mv "$sedtmp" "$AD_ENV_FILE"
  fi
  # Single-quote the value so characters like #, $, and backticks are
  # preserved literally when the .env file is later sourced by bash.
  local safe_key="${key//\'/\'\\\'\'}"
  echo "AUTO_DRIVE_API_KEY='${safe_key}'" >> "$AD_ENV_FILE"
  chmod 600 "$AD_ENV_FILE"
  echo -e "${GREEN}✓ Saved to $AD_ENV_FILE${NC}"
}
