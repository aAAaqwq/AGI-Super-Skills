#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/home/aa/clawd/skills/qingyun-api/scripts/qingyun-common.sh
source "$SCRIPT_DIR/qingyun-common.sh"

usage() {
  cat <<'EOF'
Usage:
  ./qingyun-sd-animation.sh "start prompt" "end prompt" [--format mp4] [--frames 25] [-o output.mp4]

Description:
  Create an animation task with andreasjansson/stable-diffusion-animation,
  poll until completion, then download the result.

Options:
  --format FORMAT  Output format: mp4 or gif (default: mp4)
  --frames N       Number of animation frames, positive integer (default: 25)
  -o, --output     Output file path (default: sd-animation-YYYYmmdd-HHMMSS.<format>)
  -h, --help       Show this help message

Output:
  - Create task -> poll status -> download result
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

is_positive_int() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

is_valid_format() {
  case "$1" in
    mp4|gif) return 0 ;;
    *) return 1 ;;
  esac
}

main() {
  require_cmd jq
  require_cmd curl

  local prompt_start=""
  local prompt_end=""
  local format="mp4"
  local frames="25"
  local output=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --format)
        shift
        [[ $# -gt 0 ]] || die "--format requires a value"
        format="$1"
        is_valid_format "$format" || die "Invalid --format: $format"
        ;;
      --frames)
        shift
        [[ $# -gt 0 ]] || die "--frames requires a value"
        frames="$1"
        is_positive_int "$frames" || die "--frames must be a positive integer"
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
        if [[ -z "$prompt_start" ]]; then
          prompt_start="$1"
        elif [[ -z "$prompt_end" ]]; then
          prompt_end="$1"
        else
          die "Unexpected extra argument: $1"
        fi
        ;;
    esac
    shift
  done

  [[ -n "$prompt_start" ]] || { usage; die "Start prompt is required"; }
  [[ -n "$prompt_end" ]] || { usage; die "End prompt is required"; }

  if [[ -z "$output" ]]; then
    output="sd-animation-$(date +%Y%m%d-%H%M%S).${format}"
  fi

  local payload create_response prediction_id poll_response result_url abs_output
  payload=$(jq -n \
    --arg prompt_start "$prompt_start" \
    --arg prompt_end "$prompt_end" \
    --arg format "$format" \
    --argjson frames "$frames" \
    '{version:"andreasjansson/stable-diffusion-animation:ca1f5e306e5721e19c473e0d094e6603f0456fe759c10715fcd6c1b79242d4a5",input:{width:512,height:512,prompt_start:$prompt_start,prompt_end:$prompt_end,gif_ping_pong:true,output_format:$format,guidance_scale:7.5,prompt_strength:0.9,film_interpolation:true,num_inference_steps:50,num_animation_frames:$frames,gif_frames_per_second:20,num_interpolation_steps:5}}')

  create_response=$(qy_request POST /replicate/v1/predictions "$payload") || die "Failed to create animation task"
  prediction_id=$(echo "$create_response" | jq -r '.id // empty')
  [[ -n "$prediction_id" ]] || die "No prediction id returned"

  echo "Task created successfully"
  echo "Prediction ID: $prediction_id"
  echo "Polling status..." >&2

  poll_response=$(qy_poll GET "/replicate/v1/predictions/${prediction_id}" 8 600) || die "Animation task polling failed"

  result_url=$(echo "$poll_response" | jq -r 'if (.output | type) == "array" then .output[0] else .output end // empty')
  [[ -n "$result_url" ]] || die "No output URL returned"

  mkdir -p "$(dirname "$output")"
  qy_download "$result_url" "$output" >/dev/null || die "Failed to download animation output"
  [[ -s "$output" ]] || die "Downloaded file is empty: $output"

  abs_output=$(realpath "$output")
  echo "Animation generated successfully"
  echo "Model: andreasjansson/stable-diffusion-animation"
  echo "Format: $format"
  echo "Frames: $frames"
  echo "Saved to: $abs_output"
}

main "$@"
