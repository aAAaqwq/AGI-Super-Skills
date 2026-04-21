#!/usr/bin/env bash
# Upload a file or JSON object to Auto-Drive (3-step chunked upload)
# Usage: autodrive-upload.sh <file_path> [--json] [--compress]
# Env: AUTO_DRIVE_API_KEY (required)
# Output: CID on success (stdout), status messages on stderr

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_lib.sh
source "$SCRIPT_DIR/_lib.sh"
ad_warn_git_bash
ad_require_tools curl jq

FILE_PATH="${1:?Usage: autodrive-upload.sh <file_path> [--json] [--compress]}"
IS_JSON=false
COMPRESS=false
shift
for arg in "$@"; do
  case "$arg" in
    --json) IS_JSON=true ;;
    --compress) COMPRESS=true ;;
  esac
done

if [[ -z "${AUTO_DRIVE_API_KEY:-}" ]]; then
  echo "Error: AUTO_DRIVE_API_KEY not set." >&2
  echo "Get a free key at https://ai3.storage (sign in with Google/GitHub → Developers → Create API Key)" >&2
  exit 1
fi

if [[ ! -f "$FILE_PATH" ]]; then
  echo "Error: File not found: $FILE_PATH" >&2
  exit 1
fi

FILENAME=$(basename "$FILE_PATH")
if $IS_JSON; then
  MIME="application/json"
else
  if command -v file &>/dev/null; then
    MIME=$(file --mime-type -b "$FILE_PATH" 2>/dev/null || echo "application/octet-stream")
  else
    case "${FILE_PATH##*.}" in
      json)     MIME="application/json" ;;
      txt)      MIME="text/plain" ;;
      pdf)      MIME="application/pdf" ;;
      png)      MIME="image/png" ;;
      jpg|jpeg) MIME="image/jpeg" ;;
      *)        MIME="application/octet-stream" ;;
    esac
  fi
fi

AUTH_HEADERS=(-H "Authorization: Bearer $AUTO_DRIVE_API_KEY" -H "X-Auth-Provider: apikey")

# Step 1: Create upload
echo "Creating upload for '$FILENAME'..." >&2
if $COMPRESS; then
  UPLOAD_BODY=$(jq -n --arg fn "$FILENAME" --arg mt "$MIME" \
    '{filename: $fn, mimeType: $mt, uploadOptions: {compression: {algorithm: "ZLIB"}}}')
else
  UPLOAD_BODY=$(jq -n --arg fn "$FILENAME" --arg mt "$MIME" \
    '{filename: $fn, mimeType: $mt, uploadOptions: {}}')
fi

RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "$AD_API_BASE/uploads/file" \
  "${AUTH_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "$UPLOAD_BODY")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Error: Failed to create upload (HTTP $HTTP_CODE)" >&2
  echo "$BODY" >&2
  exit 1
fi

UPLOAD_ID=$(echo "$BODY" | jq -r '.id')
if [[ -z "$UPLOAD_ID" || "$UPLOAD_ID" == "null" ]]; then
  echo "Error: Failed to create upload — no upload ID returned" >&2
  echo "$BODY" >&2
  exit 1
fi

# Step 2: Upload chunk
echo "Uploading file data..." >&2
RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "$AD_API_BASE/uploads/file/$UPLOAD_ID/chunk" \
  "${AUTH_HEADERS[@]}" \
  -F "file=@$FILE_PATH" \
  -F "index=0")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  BODY=$(echo "$RESPONSE" | sed '$d')
  echo "Error: Failed to upload chunk (HTTP $HTTP_CODE)" >&2
  echo "$BODY" >&2
  exit 1
fi

# Step 3: Complete upload → get CID
echo "Completing upload..." >&2
RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "$AD_API_BASE/uploads/$UPLOAD_ID/complete" \
  "${AUTH_HEADERS[@]}")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Error: Failed to complete upload (HTTP $HTTP_CODE)" >&2
  echo "$BODY" >&2
  exit 1
fi

CID=$(echo "$BODY" | jq -r '.cid')
if [[ -z "$CID" || "$CID" == "null" ]]; then
  echo "Error: Upload completed but no CID returned" >&2
  echo "$BODY" >&2
  exit 1
fi

# Validate CID format to prevent command injection and chain corruption
if ! ad_valid_cid "$CID"; then
  echo "Error: Invalid CID format returned: $CID" >&2
  exit 1
fi

echo "Upload successful! CID: $CID" >&2
echo "Gateway URL: https://gateway.autonomys.xyz/file/$CID" >&2
echo "$CID"
