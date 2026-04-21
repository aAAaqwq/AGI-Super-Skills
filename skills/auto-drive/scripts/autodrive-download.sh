#!/usr/bin/env bash
# Download a file from Auto-Drive by CID
# Usage: autodrive-download.sh <cid> [output_path]
# Tries the public download API first (handles server-side decompression); falls back to
# the public gateway if the API fails. Auth headers are sent when AUTO_DRIVE_API_KEY is set.
# If output_path is omitted, outputs to stdout.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_lib.sh
source "$SCRIPT_DIR/_lib.sh"
ad_warn_git_bash
ad_require_tools curl

CID="${1:?Usage: autodrive-download.sh <cid> [output_path]}"
OUTPUT="${2:-}"

# Validate CID format
if ! ad_valid_cid "$CID"; then
  echo "Error: Invalid CID format: $CID" >&2
  exit 1
fi

# Validate output path: reject traversal, resolve physically, verify within $HOME.
if [[ -n "$OUTPUT" ]]; then
  if [[ "$OUTPUT" == *..* ]]; then
    echo "Error: Output path must not contain '..': $OUTPUT" >&2; exit 1
  fi
  OUTPUT_DIR_PART="$(dirname "$OUTPUT")"
  OUTPUT_BASE="$(basename "$OUTPUT")"
  OUTPUT_RESOLVED="$(cd "$OUTPUT_DIR_PART" 2>/dev/null && pwd -P)/$OUTPUT_BASE" || {
    echo "Error: Could not resolve output path — directory does not exist: $OUTPUT_DIR_PART" >&2; exit 1
  }
  HOME_REAL="$(cd "$HOME" && pwd -P)"
  if [[ "$OUTPUT_RESOLVED" != "$HOME_REAL/"* ]]; then
    echo "Error: Output path must be within home directory" >&2
    exit 1
  fi
  OUTPUT="$OUTPUT_RESOLVED"
fi

GATEWAY="https://gateway.autonomys.xyz"

download_to_file() {
  local URL="$1" DEST="$2"
  shift 2
  RESPONSE=$(curl -sS -w "\n%{http_code}" "$URL" "$@" -o "$DEST")
  echo "$RESPONSE" | tail -1
}

# Send auth headers when API key is available (gives user-level access);
# the download API is public either way and handles server-side decompression.
AUTH_ARGS=()
if [[ -n "${AUTO_DRIVE_API_KEY:-}" ]]; then
  AUTH_ARGS=(-H "Authorization: Bearer $AUTO_DRIVE_API_KEY" -H "X-Auth-Provider: apikey")
fi

if [[ -z "$OUTPUT" ]]; then
  # Output to stdout — try download API first, fall back to gateway
  curl -sS --fail "$AD_DOWNLOAD_API/downloads/$CID" "${AUTH_ARGS[@]}" 2>/dev/null \
    || curl -sS --fail "$GATEWAY/file/$CID"
else
  # Output to file — check HTTP codes for proper error reporting
  HTTP_CODE=$(download_to_file "$AD_DOWNLOAD_API/downloads/$CID" "$OUTPUT" "${AUTH_ARGS[@]}")
  if [[ "$HTTP_CODE" -ge 200 && "$HTTP_CODE" -lt 300 ]]; then
    echo "Saved to: $OUTPUT" >&2
  else
    echo "Error: API download failed (HTTP $HTTP_CODE) — trying gateway" >&2
    HTTP_CODE=$(download_to_file "$GATEWAY/file/$CID" "$OUTPUT")
    if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
      echo "Error: Gateway download also failed (HTTP $HTTP_CODE)" >&2
      rm -f "$OUTPUT"
      exit 1
    fi
    echo "Saved to: $OUTPUT (via public gateway — file may be in compressed form)" >&2
  fi
fi
