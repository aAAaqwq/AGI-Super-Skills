#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/home/aa/clawd/skills/qingyun-api/scripts/qingyun-common.sh
source "$SCRIPT_DIR/qingyun-common.sh"

usage() {
  cat <<'EOF'
Usage:
  ./qingyun-video-kling.sh "prompt" --image URL_OR_BASE64 [--model kling-v2-5-turbo] [--duration 5] [-o output.mp4]

Description:
  Create a video from an image with Kling image2video models via:
    POST /kling/v1/videos/image2video
    GET  /kling/v1/videos/image2video/{task_id}

Options:
  --image URL_OR_BASE64   Required. Image URL or base64-encoded image data
  --model MODEL           Model name (default: kling-v2-5-turbo)
                          Example: kling-v2-5-turbo
  --duration SECONDS      Duration in seconds (default: 5)
  --aspect-ratio RATIO    Aspect ratio, e.g. 16:9, 9:16, 1:1
  --mode MODE             Mode: std | pro (default: std)
  --cfg-scale FLOAT       CFG scale value (default: 0.5)
  --negative-prompt TEXT  Negative prompt
  -o, --output FILE       Output mp4 path (default: kling-video-YYYYmmdd-HHMMSS.mp4)
  -h, --help              Show this help message

Examples:
  ./qingyun-video-kling.sh "woman waving hello" --image https://example.com/photo.jpg
  ./qingyun-video-kling.sh "snow falling" --image https://example.com/winter.jpg --model kling-v2-5-turbo --duration 10
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

is_valid_mode() {
  case "$1" in
    std|pro) return 0 ;;
    *) return 1 ;;
  esac
}

is_float() {
  [[ "$1" =~ ^[0-9]+(\.[0-9]+)?$ ]]
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

  local prompt=""
  local image=""
  local model="kling-v2-5-turbo"
  local duration="5"
  local aspect_ratio=""
  local mode="std"
  local cfg_scale="0.5"
  local negative_prompt=""
  local output=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --image)
        shift
        [[ $# -gt 0 ]] || die "--image requires a value"
        image="$1"
        ;;
      --model)
        shift
        [[ $# -gt 0 ]] || die "--model requires a value"
        model="$1"
        ;;
      --duration)
        shift
        [[ $# -gt 0 ]] || die "--duration requires a value"
        duration="$1"
        is_positive_int "$duration" || die "--duration must be a positive integer"
        ;;
      --aspect-ratio)
        shift
        [[ $# -gt 0 ]] || die "--aspect-ratio requires a value"
        aspect_ratio="$1"
        ;;
      --mode)
        shift
        [[ $# -gt 0 ]] || die "--mode requires a value"
        mode="$1"
        is_valid_mode "$mode" || die "--mode must be std or pro"
        ;;
      --cfg-scale)
        shift
        [[ $# -gt 0 ]] || die "--cfg-scale requires a value"
        cfg_scale="$1"
        is_float "$cfg_scale" || die "--cfg-scale must be a number"
        ;;
      --negative-prompt)
        shift
        [[ $# -gt 0 ]] || die "--negative-prompt requires a value"
        negative_prompt="$1"
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
  [[ -n "$image" ]] || { usage; die "--image is required"; }

  [[ -n "$output" ]] || output="kling-video-$(date +%Y%m%d-%H%M%S).mp4"

  local payload create_response task_id poll_response result_url abs_output
  payload=$(jq -n \
    --arg model_name "$model" \
    --arg image "$image" \
    --arg prompt "$prompt" \
    --arg negative_prompt "$negative_prompt" \
    --arg duration "$duration" \
    --arg aspect_ratio "$aspect_ratio" \
    --arg mode "$mode" \
    --arg cfg_scale "$cfg_scale" \
    '{
      model_name: $model_name,
      image: $image,
      image_tail: "",
      prompt: $prompt,
      negative_prompt: $negative_prompt,
      duration: $duration,
      aspect_ratio: (if $aspect_ratio != "" then $aspect_ratio else "16:9" end),
      mode: $mode,
      cfg_scale: ($cfg_scale | tonumber)
    }')

  create_response=$(qy_request POST /kling/v1/videos/image2video "$payload") || die "Failed to create kling image2video task"
  task_id=$(extract_task_id "$create_response")
  [[ -n "$task_id" ]] || die "No task id returned from create response: $create_response"

  echo "Task created successfully"
  echo "Task ID: $task_id"
  echo "Model: $model"
  echo "Polling status..." >&2

  poll_response=$(qy_poll GET "/kling/v1/videos/image2video/${task_id}" 10 1800) || die "Kling image2video task polling failed"
  result_url=$(extract_video_url "$poll_response")
  [[ -n "$result_url" ]] || die "Task completed but no video URL found in response: $poll_response"

  mkdir -p "$(dirname "$output")"
  qy_download "$result_url" "$output" >/dev/null || die "Failed to download video"
  [[ -s "$output" ]] || die "Downloaded file is empty: $output"

  abs_output=$(realpath "$output")
  echo "Video generated successfully"
  echo "Model: $model"
  echo "Saved to: $abs_output"
}

main "$@"
