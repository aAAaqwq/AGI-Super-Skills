#!/usr/bin/env bash
# Verify Auto-Drive setup — checks API key, account info, and remaining credits
# Usage: ./scripts/verify-setup.sh

set -euo pipefail

# shellcheck source=_lib.sh
source "$(dirname "$0")/_lib.sh"

ad_warn_git_bash

echo ""
echo "=== Auto-Drive Setup Verification ==="
echo ""

# Check prerequisites first — curl and jq are needed for verification below
MISSING=()
for bin in curl jq file; do
  if command -v "$bin" &>/dev/null; then
    echo -e "  ${GREEN}✓ $bin${NC}"
  else
    echo -e "  ${RED}✗ $bin not found${NC}"
    MISSING+=("$bin")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo -e "${RED}✗ Missing prerequisites: ${MISSING[*]}${NC}" >&2
  exit 1
fi
echo ""

# Check for API key
if [[ -z "${AUTO_DRIVE_API_KEY:-}" ]]; then
  echo -e "${RED}✗ AUTO_DRIVE_API_KEY is not set${NC}" >&2
  echo "  Run: scripts/setup-auto-drive.sh" >&2
  exit 1
fi
echo -e "${GREEN}✓ AUTO_DRIVE_API_KEY is set${NC}"

# Verify key and fetch account info
if ! autodrive_verify_key "$AUTO_DRIVE_API_KEY"; then
  echo "  The key may be invalid or expired. Run: scripts/update-api-key.sh" >&2
  exit 1
fi

# Display account details (AD_VERIFY_BODY set by autodrive_verify_key)
LIMIT=$(echo "$AD_VERIFY_BODY" | jq -r '.uploadLimit // .limits.uploadLimit // empty' 2>/dev/null || true)
USED=$(echo "$AD_VERIFY_BODY" | jq -r '.uploadedBytes // .limits.uploadedBytes // empty' 2>/dev/null || true)

if [[ -n "$LIMIT" && -n "$USED" ]]; then
  REMAINING=$((LIMIT - USED))
  if command -v bc &>/dev/null; then
    UNIT="MB"
    LIMIT_FMT=$(echo "scale=1; $LIMIT / 1048576" | bc)
    USED_FMT=$(echo "scale=1; $USED / 1048576" | bc)
    REMAINING_FMT=$(echo "scale=1; $REMAINING / 1048576" | bc)
  else
    UNIT="bytes"
    LIMIT_FMT="$LIMIT"
    USED_FMT="$USED"
    REMAINING_FMT="$REMAINING"
  fi
  echo "  Upload limit:    ${LIMIT_FMT} ${UNIT} / month"
  echo "  Used this month: ${USED_FMT} ${UNIT}"
  if [[ "$REMAINING" -lt 1048576 ]]; then
    echo -e "  Remaining:       ${YELLOW}${REMAINING_FMT} ${UNIT} (low)${NC}"
  else
    echo -e "  Remaining:       ${GREEN}${REMAINING_FMT} ${UNIT}${NC}"
  fi
fi

echo ""
echo -e "${GREEN}All checks passed. Auto-Drive is ready.${NC}"
echo ""
echo "Try: scripts/autodrive-upload.sh /path/to/any/file"
echo ""
