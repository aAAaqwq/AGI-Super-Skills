#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/home/aa/clawd/skills/qingyun-api/scripts/qingyun-common.sh
source "$SCRIPT_DIR/qingyun-common.sh"

usage() {
  cat <<'EOF'
Usage:
  ./qingyun-image-gemini.sh "prompt" [--ratio 16:9] [-o output.jpg]

Description:
  Generate an image with model gemini-3-pro-image-preview.

Options:
  --ratio RATIO    Aspect ratio. Allowed: 1:1, 3:4, 4:3, 9:16, 16:9
  -o, --output     Output image path (default: gemini-image-YYYYmmdd-HHMMSS.jpg)
  -h, --help       Show this help message

Output:
  - Decode base64 image and save it locally
  - Print saved path
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

is_valid_ratio() {
  case "$1" in
    1:1|3:4|4:3|9:16|16:9) return 0 ;;
    *) return 1 ;;
  esac
}

main() {
  require_cmd jq
  require_cmd base64

  local prompt=""
  local ratio="16:9"
  local output=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --ratio)
        shift
        [[ $# -gt 0 ]] || die "--ratio requires a value"
        ratio="$1"
        is_valid_ratio "$ratio" || die "Invalid --ratio: $ratio"
        ;;
      -o|--output)
        shift
        [[ $# -gt 0 ]] || die "--output requires a value"
        output="$1"
        ;;
      --*)
        die "Unknown option: $1"
        ;;
      *)
        if [[ -z "$prompt" ]]; then
          prompt="$1"
        else
          die "Unexpected extra argument: $1"
        fi
        ;;
    esac
    shift
  done

  [[ -n "$prompt" ]] || { usage; die "Prompt is required"; }

  if [[ -z "$output" ]]; then
    output="gemini-image-$(date +%Y%m%d-%H%M%S).jpg"
  fi

  local payload response b64 mime ext final_output abs_output
  payload=$(jq -n --arg prompt "$prompt" --arg ratio "$ratio" '{contents:[{parts:[{text:$prompt}]}],generationConfig:{responseModalities:["TEXT","IMAGE"],imageConfig:{aspectRatio:$ratio}}}')
  response=$(qy_gemini /v1beta/models/gemini-3-pro-image-preview:generateContent "$payload") || die "Gemini image generation request failed"

  b64=$(echo "$response" | jq -r '.candidates[0].content.parts[] | select(.inlineData) | .inlineData.data' | head -1)
  mime=$(echo "$response" | jq -r '.candidates[0].content.parts[] | select(.inlineData) | .inlineData.mimeType' | head -1)

  [[ -n "$b64" && "$b64" != "null" ]] || die "No base64 image data returned"

  ext="jpg"
  case "$mime" in
    image/png) ext="png" ;;
    image/webp) ext="webp" ;;
    image/jpeg|image/jpg|""|null) ext="jpg" ;;
    image/*) ext="${mime#image/}" ;;
  esac

  mkdir -p "$(dirname "$output")"
  final_output="$output"
  if [[ "$final_output" != *.* ]]; then
    final_output="${final_output}.${ext}"
  fi

  echo "$b64" | base64 -d > "$final_output" || die "Failed to decode image data"
  [[ -s "$final_output" ]] || die "Saved image is empty: $final_output"

  abs_output=$(realpath "$final_output")
  echo "Image generated successfully"
  echo "Model: gemini-3-pro-image-preview"
  echo "Aspect ratio: $ratio"
  echo "MIME type: ${mime:-image/jpeg}"
  echo "Saved to: $abs_output"
}

main "$@"
