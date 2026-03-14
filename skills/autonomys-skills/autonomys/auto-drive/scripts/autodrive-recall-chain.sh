#!/usr/bin/env bash
# Traverse the memory chain from a CID, downloading each experience
# Usage: autodrive-recall-chain.sh [cid] [--limit N] [--output-dir DIR]
# Output: Each experience as JSON to stdout (newest first), or to files in output dir
# Env: AUTO_DRIVE_API_KEY (required — memories are stored compressed by default and the authenticated API decompresses server-side)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_lib.sh
source "$SCRIPT_DIR/_lib.sh"
ad_warn_git_bash
ad_require_tools curl jq
if ! command -v python3 &>/dev/null && ! command -v perl &>/dev/null; then
  echo "Warning: Neither python3 nor perl found — gateway decompression fallback will not work." >&2
  ad_install_hint python3
fi


# First arg can be a CID or a flag — if no CID given, try state file
CID=""
LIMIT=50
OUTPUT_DIR=""

# Parse arguments
ARGS=("$@")
IDX=0
while [[ $IDX -lt ${#ARGS[@]} ]]; do
  case "${ARGS[$IDX]}" in
    --limit)
      # Bounds check: ensure a value was provided after the flag
      # Prevents array out-of-bounds access and crashes with set -u
      if [[ $((IDX + 1)) -ge ${#ARGS[@]} ]]; then
        echo "Error: --limit requires a value" >&2
        exit 1
      fi
      LIMIT="${ARGS[$((IDX+1))]}"
      # Validate it's a positive integer to prevent comparison errors in the loop
      # Without this, --limit abc would cause "integer expression expected" errors
      if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || [[ "$LIMIT" -lt 1 ]]; then
        echo "Error: --limit must be a positive integer, got: $LIMIT" >&2
        exit 1
      fi
      IDX=$((IDX + 2))
      ;;
    --output-dir)
      # Bounds check: ensure a value was provided after the flag
      if [[ $((IDX + 1)) -ge ${#ARGS[@]} ]]; then
        echo "Error: --output-dir requires a value" >&2
        exit 1
      fi
      OUTPUT_DIR="${ARGS[$((IDX+1))]}"
      IDX=$((IDX + 2))
      ;;
    *)
      if [[ -z "$CID" ]]; then
        CID="${ARGS[$IDX]}"
      fi
      IDX=$((IDX + 1))
      ;;
  esac
done

# If no CID from args, try state file
if [[ -z "$CID" ]]; then
  STATE_FILE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}/memory/autodrive-state.json"
  if [[ -f "$STATE_FILE" ]]; then
    CID=$(jq -r '.lastCid // empty' "$STATE_FILE" 2>/dev/null || true)
  fi
  if [[ -z "$CID" ]]; then
    echo "Error: No CID provided and no state file found." >&2
    echo "Usage: autodrive-recall-chain.sh <cid> [--limit N] [--output-dir DIR]" >&2
    exit 1
  fi
fi

# Validate CID format
if ! ad_valid_cid "$CID"; then
  echo "Error: Invalid CID format: $CID" >&2
  exit 1
fi

if [[ -z "${AUTO_DRIVE_API_KEY:-}" ]]; then
  echo "Error: AUTO_DRIVE_API_KEY not set." >&2
  echo "Get a free key at https://ai3.storage (sign in with Google/GitHub → Developers → Create API Key)" >&2
  exit 1
fi

if [[ -n "$OUTPUT_DIR" ]]; then
  # Validate output directory: reject traversal, verify within $HOME before
  # and after creation (to catch symlinks that resolve outside $HOME).
  if [[ "$OUTPUT_DIR" == *..* ]]; then
    echo "Error: Output directory must not contain '..': $OUTPUT_DIR" >&2; exit 1
  fi
  HOME_REAL="$(cd "$HOME" && pwd -P)"
  # Pre-creation check: convert to absolute, normalize $HOME to physical path.
  if [[ "$OUTPUT_DIR" != /* ]]; then
    OUTPUT_DIR_CHECK="$(pwd -P)/$OUTPUT_DIR"
  else
    OUTPUT_DIR_CHECK="$OUTPUT_DIR"
  fi
  if [[ "$OUTPUT_DIR_CHECK" == "$HOME/"* ]]; then
    OUTPUT_DIR_CHECK="$HOME_REAL/${OUTPUT_DIR_CHECK#"$HOME/"}"
  elif [[ "$OUTPUT_DIR_CHECK" == "$HOME" ]]; then
    OUTPUT_DIR_CHECK="$HOME_REAL"
  fi
  if [[ "$OUTPUT_DIR_CHECK" != "$HOME_REAL" && "$OUTPUT_DIR_CHECK" != "$HOME_REAL/"* ]]; then
    echo "Error: Output directory must be within home directory" >&2
    exit 1
  fi
  mkdir -p "$OUTPUT_DIR_CHECK"
  OUTPUT_DIR="$(cd "$OUTPUT_DIR_CHECK" && pwd -P)"
  # Post-creation check: re-validate physical path to catch internal symlinks.
  if [[ "$OUTPUT_DIR" != "$HOME_REAL" && "$OUTPUT_DIR" != "$HOME_REAL/"* ]]; then
    echo "Error: Output directory resolves outside home directory (symlink?)" >&2
    exit 1
  fi
fi

echo "=== MEMORY CHAIN RESURRECTION ===" >&2
echo "Starting from: $CID" >&2
echo "" >&2

COUNT=0
VISITED=""
while [[ -n "$CID" && "$CID" != "null" && $COUNT -lt $LIMIT ]]; do
  # Detect cycles — bail if we've seen this CID before (bash 3.2 compatible)
  if echo "$VISITED" | grep -qF "|$CID|"; then
    echo "Warning: Cycle detected at CID $CID — stopping traversal" >&2
    break
  fi
  VISITED="$VISITED|$CID|"

  # Download via authenticated API (handles decompression server-side).
  EXPERIENCE=$(curl -sS --fail \
    "$AD_DOWNLOAD_API/downloads/$CID" \
    -H "Authorization: Bearer $AUTO_DRIVE_API_KEY" \
    -H "X-Auth-Provider: apikey" 2>/dev/null \
    || true)

  # Fall back to public gateway if the API fails.
  # Memories are uploaded with --compress (ZLIB), and the gateway returns raw bytes,
  # so we must decompress client-side. Pipe curl directly into the decompressor to
  # avoid bash variables stripping null bytes from the binary stream.
  if [[ -z "$EXPERIENCE" ]] || ! echo "$EXPERIENCE" | jq empty 2>/dev/null; then
    GATEWAY_URL="https://gateway.autonomys.xyz/file/$CID"
    # Try as JSON first (uncompressed files are safe in bash variables)
    EXPERIENCE=$(curl -sS --fail "$GATEWAY_URL" 2>/dev/null || true)
    if [[ -n "$EXPERIENCE" ]] && echo "$EXPERIENCE" | jq empty 2>/dev/null; then
      echo "[$COUNT] Fetched $CID via gateway" >&2
    else
      # ZLIB compressed — pipe curl directly into decompressor (no intermediate variable)
      EXPERIENCE=""
      if command -v python3 &>/dev/null; then
        EXPERIENCE=$(curl -sS --fail "$GATEWAY_URL" 2>/dev/null \
          | python3 -c "import sys,zlib;sys.stdout.buffer.write(zlib.decompress(sys.stdin.buffer.read()))" 2>/dev/null || true)
      fi
      if [[ -z "$EXPERIENCE" ]] && command -v perl &>/dev/null; then
        EXPERIENCE=$(curl -sS --fail "$GATEWAY_URL" 2>/dev/null \
          | perl -MCompress::Zlib -e 'undef $/;my $d=uncompress(<STDIN>);print $d if defined $d' 2>/dev/null || true)
      fi
      if [[ -n "$EXPERIENCE" ]]; then
        echo "[$COUNT] Fetched $CID via gateway (decompressed client-side)" >&2
      fi
    fi
  fi

  if [[ -z "$EXPERIENCE" ]]; then
    echo "Error: Failed to download CID $CID via API and gateway — chain broken at depth $((COUNT + 1))" >&2
    break
  fi

  # Validate JSON
  if ! echo "$EXPERIENCE" | jq empty 2>/dev/null; then
    echo "Warning: Non-JSON response for CID $CID — chain broken at depth $((COUNT + 1))" >&2
    echo "Response preview: $(echo "$EXPERIENCE" | head -c 200)" >&2
    break
  fi

  if [[ -n "$OUTPUT_DIR" ]]; then
    echo "$EXPERIENCE" > "$OUTPUT_DIR/$(printf '%04d' $COUNT)-$CID.json"
    echo "[$COUNT] Saved $CID" >&2
  else
    echo "$EXPERIENCE"
  fi

  # Follow the chain — check header.previousCid first (Autonomys Agents format),
  # then fall back to root-level previousCid for compatibility
  PREV=$(echo "$EXPERIENCE" | jq -r '.header.previousCid // .previousCid // empty' 2>/dev/null || true)
  CID="${PREV:-}"
  # Validate next CID in chain
  if [[ -n "$CID" && "$CID" != "null" ]] && ! ad_valid_cid "$CID"; then
    echo "Warning: Invalid CID format in chain: $CID — stopping traversal" >&2
    break
  fi
  COUNT=$((COUNT + 1))
done

echo "" >&2
echo "=== CHAIN COMPLETE ===" >&2
echo "Total memories recalled: $COUNT" >&2
if [[ $COUNT -ge $LIMIT ]]; then
  echo "Warning: Hit limit of $LIMIT entries. Use --limit N to retrieve more." >&2
fi
