#!/usr/bin/env bash
# Save a memory experience to Auto-Drive as part of the linked list chain
# Usage: autodrive-save-memory.sh <data_file_or_string> [--agent-name NAME] [--state-file PATH]
# Env: AUTO_DRIVE_API_KEY (required), AGENT_NAME (optional, default: openclaw-agent),
#      OPENCLAW_WORKSPACE (optional, default: $HOME/.openclaw/workspace)
# Output: JSON with cid, previousCid, chainLength (stdout)
#
# If the first argument is a file path, its contents are used as the data payload.
# If the first argument is a plain string, it is wrapped as {"type":"memory","content":"..."}.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_lib.sh
source "$SCRIPT_DIR/_lib.sh"
ad_warn_git_bash
ad_require_tools curl jq
INPUT="${1:?Usage: autodrive-save-memory.sh <data_file_or_string> [--agent-name NAME] [--state-file PATH]}"
AGENT_NAME="${AGENT_NAME:-openclaw-agent}"
STATE_FILE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}/memory/autodrive-state.json"
STATE_FILE_EXPLICIT=false

shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent-name)
      if [[ $# -lt 2 ]]; then echo "Error: --agent-name requires a value" >&2; exit 1; fi
      AGENT_NAME="$2"; shift 2 ;;
    --state-file)
      if [[ $# -lt 2 ]]; then echo "Error: --state-file requires a value" >&2; exit 1; fi
      STATE_FILE="$2"; STATE_FILE_EXPLICIT=true; shift 2 ;;
    *) shift ;;
  esac
done

# Validate explicit --state-file: reject traversal, resolve physically, verify within $HOME.
# Skipped for the default path which derives from a trusted env var.
if [[ "$STATE_FILE_EXPLICIT" == true ]]; then
  if [[ "$STATE_FILE" == *..* ]]; then
    echo "Error: State file path must not contain '..': $STATE_FILE" >&2; exit 1
  fi
  HOME_REAL="$(cd "$HOME" && pwd -P)"
  # Convert to absolute, normalize $HOME to physical path.
  if [[ "$STATE_FILE" != /* ]]; then
    STATE_FILE_CHECK="$(pwd -P)/$STATE_FILE"
  else
    STATE_FILE_CHECK="$STATE_FILE"
  fi
  if [[ "$STATE_FILE_CHECK" == "$HOME/"* ]]; then
    STATE_FILE_CHECK="$HOME_REAL/${STATE_FILE_CHECK#"$HOME/"}"
  elif [[ "$STATE_FILE_CHECK" == "$HOME" ]]; then
    STATE_FILE_CHECK="$HOME_REAL"
  fi
  # Resolve parent physically if it exists (catches symlinks).
  STATE_FILE_DIR="$(dirname "$STATE_FILE_CHECK")"
  STATE_FILE_BASE="$(basename "$STATE_FILE_CHECK")"
  if [[ -d "$STATE_FILE_DIR" ]]; then
    STATE_FILE_CHECK="$(cd "$STATE_FILE_DIR" && pwd -P)/$STATE_FILE_BASE"
  fi
  if [[ "$STATE_FILE_CHECK" != "$HOME_REAL/"* ]]; then
    echo "Error: State file path must be within home directory" >&2
    exit 1
  fi
  STATE_FILE="$STATE_FILE_CHECK"
fi

if [[ -z "${AUTO_DRIVE_API_KEY:-}" ]]; then
  echo "Error: AUTO_DRIVE_API_KEY not set." >&2
  echo "Get a free key at https://ai3.storage (sign in with Google/GitHub → Developers → Create API Key)" >&2
  exit 1
fi

# Determine if input is a file or a string
if [[ -f "$INPUT" ]]; then
  # Validate it's JSON
  if ! jq empty "$INPUT" 2>/dev/null; then
    echo "Error: Data file is not valid JSON: $INPUT" >&2
    exit 1
  fi
  DATA_JSON=$(cat "$INPUT")
else
  # Wrap the plain string as a simple memory object
  DATA_JSON=$(jq -n --arg content "$INPUT" '{type: "memory", content: $content}')
fi

# Read previous CID and chain length from state file
PREVIOUS_CID="null"
CHAIN_LENGTH=0
if [[ -f "$STATE_FILE" ]]; then
  PREVIOUS_CID=$(jq -r '.lastCid // empty' "$STATE_FILE" 2>/dev/null || echo "null")
  CHAIN_LENGTH=$(jq -r '.chainLength // 0' "$STATE_FILE" 2>/dev/null || echo "0")
  [[ -z "$PREVIOUS_CID" ]] && PREVIOUS_CID="null"
  # Reject a corrupted/tampered state file CID rather than propagating it into the chain
  if [[ "$PREVIOUS_CID" != "null" ]] && ! ad_valid_cid "$PREVIOUS_CID"; then
    echo "Warning: State file contains invalid CID '$PREVIOUS_CID' — starting new chain" >&2
    PREVIOUS_CID="null"
    CHAIN_LENGTH=0
  fi
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

# Build the experience JSON with header/data structure
EXPERIENCE=$(jq -n \
  --arg name "$AGENT_NAME" \
  --arg ts "$TIMESTAMP" \
  --arg prev "$PREVIOUS_CID" \
  --argjson data "$DATA_JSON" \
  '{
    header: {
      agentName: $name,
      agentVersion: "1.0.0",
      timestamp: $ts,
      previousCid: (if $prev == "null" then null else $prev end)
    },
    data: $data
  }')

# Write to temp file and upload via the upload script
TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT
echo "$EXPERIENCE" > "$TMPFILE"
CID=$("$SCRIPT_DIR/autodrive-upload.sh" "$TMPFILE" --json --compress)

if [[ -z "$CID" ]]; then
  echo "Error: Upload failed — no CID returned" >&2
  exit 1
fi

# Validate CID format
if ! ad_valid_cid "$CID"; then
  echo "Error: Invalid CID format returned: $CID" >&2
  exit 1
fi

# Update state file
NEW_LENGTH=$((CHAIN_LENGTH + 1))
mkdir -p "$(dirname "$STATE_FILE")"
jq -n \
  --arg cid "$CID" \
  --arg ts "$TIMESTAMP" \
  --argjson len "$NEW_LENGTH" \
  '{lastCid: $cid, lastUploadTimestamp: $ts, chainLength: $len}' > "$STATE_FILE"
chmod 600 "$STATE_FILE"

# Pin latest CID to MEMORY.md for session continuity (if it exists)
MEMORY_FILE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}/MEMORY.md"
if [[ -f "$MEMORY_FILE" ]]; then
  if grep -q "^## Auto-Drive Chain" "$MEMORY_FILE"; then
    if grep -q "^\- \*\*Latest CID:\*\*" "$MEMORY_FILE"; then
      # Portable sed -i (works on both macOS and Linux)
      SEDTMP=$(mktemp "${MEMORY_FILE}.XXXXXX")
      sed "s|^- \*\*Latest CID:\*\*.*|- **Latest CID:** \`$CID\` (chain length: $NEW_LENGTH, updated: $TIMESTAMP)|" "$MEMORY_FILE" > "$SEDTMP" && mv "$SEDTMP" "$MEMORY_FILE"
    else
      # Backticks below are literal Markdown, not shell expansion
      # shellcheck disable=SC2016
      printf '- **Latest CID:** `%s` (chain length: %d, updated: %s)\n' "$CID" "$NEW_LENGTH" "$TIMESTAMP" >> "$MEMORY_FILE"
    fi
  else
    # Backticks below are literal Markdown, not shell expansion
    # shellcheck disable=SC2016
    printf '\n## Auto-Drive Chain\n- **Latest CID:** `%s` (chain length: %d, updated: %s)\n' "$CID" "$NEW_LENGTH" "$TIMESTAMP" >> "$MEMORY_FILE"
  fi
fi

# Output structured result
jq -n \
  --arg cid "$CID" \
  --arg prev "$PREVIOUS_CID" \
  --argjson len "$NEW_LENGTH" \
  '{cid: $cid, previousCid: (if $prev == "null" then null else $prev end), chainLength: $len}'
