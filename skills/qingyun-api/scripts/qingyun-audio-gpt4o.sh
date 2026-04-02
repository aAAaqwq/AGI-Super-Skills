#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/home/aa/clawd/skills/qingyun-api/scripts/qingyun-common.sh
source "$SCRIPT_DIR/qingyun-common.sh"

usage() {
  cat <<'EOF'
Usage:
  ./qingyun-audio-gpt4o.sh "say hello" [--voice alloy] [--format mp3] [-o output.mp3]

Description:
  Generate audio with model gpt-4o-audio-preview and save it locally.

Options:
  --voice VOICE    Voice: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer
  --format FORMAT  Audio format: wav, mp3, flac, opus, pcm16 (default: mp3)
  -o, --output     Output file path (default: gpt4o-audio-YYYYmmdd-HHMMSS.<format>)
  -h, --help       Show this help message

Output:
  - Decode base64 audio and save it locally
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

is_valid_voice() {
  case "$1" in
    alloy|ash|ballad|coral|echo|fable|nova|onyx|sage|shimmer) return 0 ;;
    *) return 1 ;;
  esac
}

is_valid_format() {
  case "$1" in
    wav|mp3|flac|opus|pcm16) return 0 ;;
    *) return 1 ;;
  esac
}

main() {
  require_cmd jq
  require_cmd base64

  local text=""
  local voice="alloy"
  local format="mp3"
  local output=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --voice)
        shift
        [[ $# -gt 0 ]] || die "--voice requires a value"
        voice="$1"
        is_valid_voice "$voice" || die "Invalid --voice: $voice"
        ;;
      --format)
        shift
        [[ $# -gt 0 ]] || die "--format requires a value"
        format="$1"
        is_valid_format "$format" || die "Invalid --format: $format"
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
        if [[ -z "$text" ]]; then
          text="$1"
        else
          die "Unexpected extra argument: $1"
        fi
        ;;
    esac
    shift
  done

  [[ -n "$text" ]] || { usage; die "Text is required"; }

  if [[ -z "$output" ]]; then
    output="gpt4o-audio-$(date +%Y%m%d-%H%M%S).${format}"
  fi

  local payload response b64 final_output abs_output
  payload=$(jq -n \
    --arg text "$text" \
    --arg voice "$voice" \
    --arg format "$format" \
    '{model:"gpt-4o-audio-preview",modalities:["text","audio"],audio:{voice:$voice,format:$format},messages:[{role:"user",content:$text}]}')

  response=$(qy_request POST /v1/chat/completions "$payload") || die "Audio generation request failed"
  b64=$(echo "$response" | jq -r '.choices[0].message.audio.data // empty')
  [[ -n "$b64" ]] || die "No base64 audio data returned"

  mkdir -p "$(dirname "$output")"
  final_output="$output"
  if [[ "$final_output" != *.* ]]; then
    final_output="${final_output}.${format}"
  fi

  echo "$b64" | base64 -d > "$final_output" || die "Failed to decode audio data"
  [[ -s "$final_output" ]] || die "Saved audio is empty: $final_output"

  abs_output=$(realpath "$final_output")
  echo "Audio generated successfully"
  echo "Model: gpt-4o-audio-preview"
  echo "Voice: $voice"
  echo "Format: $format"
  echo "Saved to: $abs_output"
}

main "$@"
