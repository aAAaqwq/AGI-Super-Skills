#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/home/aa/clawd/skills/qingyun-api/scripts/qingyun-common.sh
source "$SCRIPT_DIR/qingyun-common.sh"

usage() {
  cat <<'EOF'
Usage:
  ./qingyun-effects-kling.sh --scene balloon_parade --image URL [--duration 5] [-o output.mp4]

Description:
  Apply Kling video effects to an image via:
    POST /kling/v1/videos/effects
    GET  /kling/v1/videos/effects/{task_id}

Options:
  --scene SCENE         Required. Effect scene name, e.g.:
                         balloon_parade, and many more (check API docs for full list)
  --image URL           Required. Source image URL
  --duration SECONDS    Duration in seconds (default: 5)
  -o, --output FILE     Output mp4 path (default: kling-effects-YYYYmmdd-HHMMSS.mp4)
  -h, --help            Show this help message

Examples:
  ./qingyun-effects-kling.sh --scene balloon_parade --image https://example.com/photo.jpg
  ./qingyun-effects-kling.sh --scene balloon_parade --image https://example.com/photo.jpg --duration 10 -o fun.mp4
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

is_url() {
  [[ "$1" =~ ^https?:// ]]
}

is_positive_int() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

extract_task_id() {
  local json="$1"
  echo "$json" | jq -r '.task_id // .id // .data.task_id // .data.id // .data.taskId // .taskId // empty'
}

extract_video_url() {
  local json="$1"
  echo "$json" | jq -r '
    .video_url //
    .url //
    .result_url //
    .output_url //
    .data.video_url //
    .data.url //
    .data.output.video_url //
    .data.output.url //
    .result.video_url //
    .result.url //
    .output.video_url //
    .output.url //
    .data.task_result.video_url //
    .data.task_result.videos[0].url //
    (if (.output | type) == "array" then .output[0] else empty end) //
    empty'
}

main() {
  require_cmd jq
  require_cmd curl
  require_cmd realpath

  local scene=""
  local image=""
  local duration="5"
  local output=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --scene)
        shift
        [[ $# -gt 0 ]] || die "--scene requires a value"
        scene="$1"
        ;;
      --image)
        shift
        [[ $# -gt 0 ]] || die "--image requires a value"
        image="$1"
        is_url "$image" || die "--image must be a URL (http(s)://)"
        ;;
      --duration)
        shift
        [[ $# -gt 0 ]] || die "--duration requires a value"
        duration="$1"
        is_positive_int "$duration" || die "--duration must be a positive integer"
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
        die "Unexpected extra argument: $1"
        ;;
    esac
    shift
  done

  [[ -n "$scene" ]] || { usage; die "--scene is required"; }
  [[ -n "$image" ]] || { usage; die "--image is required"; }

  [[ -n "$output" ]] || output="kling-effects-$(date +%Y%m%d-%H%M%S).mp4"

  local payload create_response task_id poll_response result_url abs_output
  payload=$(jq -n \
    --arg effect_scene "$scene" \
    --arg image "$image" \
    --arg duration "$duration" \
    '{
      effect_scene: $effect_scene,
      input: {
        duration: $duration,
        image: $image
      }
    }')

  create_response=$(qy_request POST /kling/v1/videos/effects "$payload") || die "Failed to create kling effects task"
  task_id=$(extract_task_id "$create_response")
  [[ -n "$task_id" ]] || die "No task id returned from create response: $create_response"

  echo "Task created successfully"
  echo "Task ID: $task_id"
  echo "Scene: $scene"
  echo "Polling status..." >&2

  poll_response=$(qy_poll GET "/kling/v1/videos/effects/${task_id}" 10 1800) || die "Kling effects task polling failed"
  result_url=$(extract_video_url "$poll_response")
  [[ -n "$result_url" ]] || die "Task completed but no video URL found in response: $poll_response"

  mkdir -p "$(dirname "$output")"
  qy_download "$result_url" "$output" >/dev/null || die "Failed to download video"
  [[ -s "$output" ]] || die "Downloaded file is empty: $output"

  abs_output=$(realpath "$output")
  echo "Effects video generated successfully"
  echo "Scene: $scene"
  echo "Saved to: $abs_output"
}

main "$@"
