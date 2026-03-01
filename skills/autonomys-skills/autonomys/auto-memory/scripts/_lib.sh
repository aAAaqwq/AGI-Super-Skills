#!/usr/bin/env bash
# Shared helpers for Auto-Memory scripts.  Source this file; do not execute it.
# Usage: source "$(dirname "$0")/_lib.sh"

# -- Constants ----------------------------------------------------------------

AD_API_BASE="https://mainnet.auto-drive.autonomys.xyz/api"
AD_DOWNLOAD_API="https://public.auto-drive.autonomys.xyz/api"
AM_OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"
AM_ENV_FILE="$AM_OPENCLAW_DIR/.env"
AM_CONFIG_FILE="$AM_OPENCLAW_DIR/openclaw.json"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# -- Platform / dependency helpers -------------------------------------------

# Print a platform-appropriate install hint for one or more packages.
# Usage: am_install_hint <pkg> [pkg ...]
am_install_hint() {
  case "$(uname -s 2>/dev/null)" in
    Linux*)               echo "  Install: sudo apt install $*" >&2 ;;
    Darwin*)              echo "  Install: brew install $*" >&2 ;;
    MINGW*|MSYS*|CYGWIN*) echo "  Install: winget install $* OR choco install $*" >&2 ;;
    *)                    echo "  Install: $*" >&2 ;;
  esac
}

# Warn Git Bash / Windows users about potential compatibility issues.
am_warn_git_bash() {
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*)
      echo "Note: Running in Git Bash. For full compatibility, consider using WSL." >&2
      echo "WSL setup: https://learn.microsoft.com/en-us/windows/wsl/install" >&2
      ;;
  esac
}

# Check that all listed commands exist; exit 1 with install hint if any are missing.
# Usage: am_require_tools curl jq
am_require_tools() {
  local _missing=()
  local _cmd
  for _cmd in "$@"; do
    command -v "$_cmd" &>/dev/null || _missing+=("$_cmd")
  done
  if [[ ${#_missing[@]} -gt 0 ]]; then
    echo -e "${RED}Error: Missing required tools: ${_missing[*]}${NC}" >&2
    am_install_hint "${_missing[@]}"
    exit 1
  fi
}

# -- Validation helpers ------------------------------------------------------

# Autonomys CID format: base32-encoded, starting with "baf".
AM_CID_RE='^baf[a-z2-7]{50,100}$'

# Return 0 if the argument looks like a valid Autonomys CID, 1 otherwise.
# Usage: am_valid_cid "$CID"
am_valid_cid() { [[ "${1:-}" =~ $AM_CID_RE ]]; }

# -- Functions ----------------------------------------------------------------

# Verify an API key against the Auto Drive accounts endpoint.
# On success, sets AM_VERIFY_BODY with the JSON response.
# On failure, prints an error to stderr and returns 1.
# Usage: automemory_verify_key "$API_KEY"
automemory_verify_key() {
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
  AM_VERIFY_BODY="$body"
  echo -e "${GREEN}✓ API key verified${NC}"
}

# Save an API key to openclaw.json and .env.
# Creates $AM_OPENCLAW_DIR if it doesn't exist.
# Temp files are cleaned up on exit via trap.
# Usage: automemory_save_key "$API_KEY"
automemory_save_key() {
  local key="$1"

  mkdir -p "$AM_OPENCLAW_DIR"
  chmod 700 "$AM_OPENCLAW_DIR"

  # Collect temp files for cleanup
  _AM_TMPS=()
  trap 'rm -f "${_AM_TMPS[@]}"' EXIT

  # --- openclaw.json ---------------------------------------------------------
  # Write to .apiKey (not .env.AUTO_DRIVE_API_KEY) — the skill declares
  # primaryEnv: AUTO_DRIVE_API_KEY, so the gateway maps .apiKey to that
  # env var automatically.  This matches the documented config path:
  # skills.entries.auto-memory.apiKey
  if [[ ! -f "$AM_CONFIG_FILE" ]]; then
    local newtmp
    newtmp=$(mktemp)
    _AM_TMPS+=("$newtmp")
    jq -n --arg key "$key" \
      '{"skills": {"entries": {"auto-memory": {"enabled": true, "apiKey": $key}}}}' \
      > "$newtmp" && mv "$newtmp" "$AM_CONFIG_FILE"
    chmod 600 "$AM_CONFIG_FILE"
  else
    local jsontmp
    jsontmp=$(mktemp)
    _AM_TMPS+=("$jsontmp")
    jq --arg key "$key" \
      '.skills //= {} | .skills.entries //= {} | .skills.entries["auto-memory"] //= {} | .skills.entries["auto-memory"].apiKey = $key | .skills.entries["auto-memory"].enabled = true' \
      "$AM_CONFIG_FILE" > "$jsontmp" && mv "$jsontmp" "$AM_CONFIG_FILE"
    chmod 600 "$AM_CONFIG_FILE"
  fi
  echo -e "${GREEN}✓ Saved to $AM_CONFIG_FILE${NC}"

  # --- .env ------------------------------------------------------------------
  # Remove any existing AUTO_DRIVE_API_KEY lines first to prevent duplicates,
  # then append exactly one entry.
  if [[ -f "$AM_ENV_FILE" ]]; then
    local sedtmp
    sedtmp=$(mktemp)
    _AM_TMPS+=("$sedtmp")
    sed '/^AUTO_DRIVE_API_KEY=/d' "$AM_ENV_FILE" > "$sedtmp" && mv "$sedtmp" "$AM_ENV_FILE"
  fi
  # Single-quote the value so characters like #, $, and backticks are
  # preserved literally when the .env file is later sourced by bash.
  local safe_key="${key//\'/\'\\\'\'}"
  echo "AUTO_DRIVE_API_KEY='${safe_key}'" >> "$AM_ENV_FILE"
  chmod 600 "$AM_ENV_FILE"
  echo -e "${GREEN}✓ Saved to $AM_ENV_FILE${NC}"
}
