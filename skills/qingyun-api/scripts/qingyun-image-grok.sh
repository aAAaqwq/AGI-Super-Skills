#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/home/aa/clawd/skills/qingyun-api/scripts/qingyun-common.sh
source "$SCRIPT_DIR/qingyun-common.sh"

usage() {
  cat <<'EOF'
Usage:
  ./qingyun-image-grok.sh "prompt" [--size 960x960] [-o output.jpg]

Description:
  Generate an image with model grok-imagine-image-pro and download it locally.

Options:
  --size SIZE      Image size. Allowed: 960x960, 720x1280, 1280x720, 1168x784, 784x1168
  -o, --output     Output image path (default: grok-image-YYYYmmdd-HHMMSS.jpg)
  -h, --help       Show this help message

Output:
  - Download image to local file
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

is_valid_size() {
  case "$1" in
    960x960|720x1280|1280x720|1168x784|784x1168) return 0 ;;
    *) return 1 ;;
  esac
}

main() {
  require_cmd jq
  require_cmd curl

  local prompt=""
  local size="960x960"
  local output=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --size)
        shift
        [[ $# -gt 0 ]] || die "--size requires a value"
        size="$1"
        is_valid_size "$size" || die "Invalid --size: $size"
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
    output="grok-image-$(date +%Y%m%d-%H%M%S).jpg"
  fi

  local payload response url abs_output
  payload=$(jq -n --arg prompt "$prompt" --arg size "$size" '{model:"grok-imagine-image-pro",prompt:$prompt,size:$size}')
  response=$(qy_request POST /v1/images/generations "$payload") || die "Image generation request failed"

  url=$(echo "$response" | jq -r '.data[0].url // empty')
  [[ -n "$url" ]] || die "No image URL returned"

  mkdir -p "$(dirname "$output")"
  qy_download "$url" "$output" >/dev/null || die "Failed to download image"
  [[ -s "$output" ]] || die "Downloaded file is empty: $output"

  abs_output=$(realpath "$output")
  echo "Image generated successfully"
  echo "Model: grok-imagine-image-pro"
  echo "Size: $size"
  echo "Saved to: $abs_output"
}

main "$@"
