#!/usr/bin/env bash
# img-gen.sh — Unified image generation with priority fallback
# Priority: qingyun-gemini → relay(boluobao → xingjiabi)
# Usage: bash img-gen.sh -p "prompt" -f "output" [-a "3:4"] [-r "1k"] [-P provider]

set -euo pipefail

PROMPT=""
OUTPUT=""
ASPECT="1:1"
RESOLUTION="1k"
FORCE_PROVIDER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p) PROMPT="$2"; shift 2 ;;
    -f) OUTPUT="$2"; shift 2 ;;
    -a) ASPECT="$2"; shift 2 ;;
    -r) RESOLUTION="$2"; shift 2 ;;
    -P) FORCE_PROVIDER="$2"; shift 2 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

if [[ -z "$PROMPT" || -z "$OUTPUT" ]]; then
  echo "Usage: bash img-gen.sh -p 'prompt' -f 'output' [-a '3:4'] [-r '1k'] [-P provider]"
  exit 1
fi

# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT")"

generate_via_qingyun() {
  local qingyun_key
  qingyun_key=$(pass show api/qingyun 2>/dev/null | head -n 1) || return 1
  if [[ -z "$qingyun_key" ]]; then return 1; fi
  
  export QINGYUN_API_KEY="$qingyun_key"
  local script="$HOME/clawd/skills/qingyun-api/scripts/qingyun-image-gemini.sh"
  if [[ ! -f "$script" ]]; then return 1; fi
  
  echo "[1/3] Trying qingyun Gemini..."
  if bash "$script" "$PROMPT" --ratio "$ASPECT" -o "$OUTPUT" 2>/dev/null; then
    echo "✅ Generated via qingyun Gemini"
    return 0
  fi
  return 1
}

generate_via_relay() {
  local relay_script="$HOME/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py"
  if [[ ! -f "$relay_script" ]]; then return 1; fi
  
  echo "[2/3] Trying relay providers (boluobao → xingjiabi)..."
  if uv run "$relay_script" -p "$PROMPT" -f "$OUTPUT" -a "$ASPECT" -r "$RESOLUTION" ${FORCE_PROVIDER:+-P "$FORCE_PROVIDER"} 2>/dev/null; then
    echo "✅ Generated via relay"
    return 0
  fi
  return 1
}

# Main priority chain
if [[ -n "$FORCE_PROVIDER" ]]; then
  # Force specific relay provider
  generate_via_relay
else
  generate_via_qingyun || generate_via_relay
fi

if [[ ! -f "$OUTPUT" ]]; then
  echo "❌ All providers failed"
  exit 1
fi
