#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/home/aa/clawd/skills/qingyun-api/scripts/qingyun-common.sh
source "$SCRIPT_DIR/qingyun-common.sh"

usage() {
  cat <<'EOF'
Usage:
  ./qingyun-video-doubao.sh "prompt" --model doubao-seedance-1-5-pro-251215 [--first-frame url] [--last-frame url] [-o output.mp4]

Description:
  Create a video with Doubao Seedance models via:
    POST /volc/v1/contents/generations/tasks
    GET  /volc/v1/contents/generations/tasks/{task_id}

Options:
  --model MODEL        Required. Supported:
                         doubao-seedance-1-5-pro-251215
                         doubao-seedance-1-0-pro-fast-251015
  --first-frame URL    Image URL for first frame reference
  --last-frame URL     Image URL for last frame reference
  -o, --output FILE    Output mp4 path (default: doubao-video-YYYYmmdd-HHMMSS.mp4)
  -h, --help           Show this help message

Examples:
  ./qingyun-video-doubao.sh "a dog running on the beach" --model doubao-seedance-1-5-pro-251215
  ./qingyun-video-doubao.sh "girl dancing" --model doubao-seedance-1-5-pro-251215 --first-frame https://example.com/photo.jpg
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

is_supported_model() {
  case "$1" in
    doubao-seedance-1-5-pro-251215|doubao-seedance-1-0-pro-fast-251015) return 0 ;;
    *) return 1 ;;
  esac
}

is_url() {
  [[ "$1" =~ ^https?:// ]]
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
    .content.video_url //
    .content.url //
    .data.video_url //
    .data.url //
    .data.content[0].url //
    .data.content.video_url //
    .data.output.video_url //
    .data.output.url //
    .result.video_url //
    .result.url //
    .output.video_url //
    .output.url //
    (if (.output | type) == "array" then .output[0] else empty end) //
    empty'
}

main() {
  require_cmd jq
  require_cmd curl
  require_cmd realpath

  local prompt=""
  local model=""
  local first_frame=""
  local last_frame=""
  local output=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --model)
        shift
        [[ $# -gt 0 ]] || die "--model requires a value"
        model="$1"
        ;;
      --first-frame)
        shift
        [[ $# -gt 0 ]] || die "--first-frame requires a value"
        first_frame="$1"
        if ! is_url "$first_frame"; then
          # 本地文件：转base64 data URI
          [[ -f "$first_frame" ]] || die "--first-frame file not found: $first_frame"
          first_frame="data:image/png;base64,$(base64 -w0 "$first_frame")"
        fi
        ;;
      --last-frame)
        shift
        [[ $# -gt 0 ]] || die "--last-frame requires a value"
        last_frame="$1"
        if ! is_url "$last_frame"; then
          # 本地文件：转base64 data URI
          [[ -f "$last_frame" ]] || die "--last-frame file not found: $last_frame"
          last_frame="data:image/png;base64,$(base64 -w0 "$last_frame")"
        fi
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
  [[ -n "$model" ]] || { usage; die "--model is required"; }
  is_supported_model "$model" || die "Unsupported --model: $model"

  [[ -n "$output" ]] || output="doubao-video-$(date +%Y%m%d-%H%M%S).mp4"

  # Build content array: text entry first, then optional image entries
  local content_json
  content_json=$(jq -n --arg text "$prompt" '[{type:"text",text:$text}]')

  if [[ -n "$first_frame" ]]; then
    content_json=$(echo "$content_json" | jq --arg url "$first_frame" \
      '. + [{type:"image_url",role:"first_frame",image_url:{url:$url}}]')
  fi

  if [[ -n "$last_frame" ]]; then
    content_json=$(echo "$content_json" | jq --arg url "$last_frame" \
      '. + [{type:"image_url",role:"last_frame",image_url:{url:$url}}]')
  fi

  local payload create_response task_id poll_response result_url abs_output
  payload=$(jq -n \
    --arg model "$model" \
    --argjson content "$content_json" \
    '{model:$model,content:$content}')

  create_response=$(qy_request POST /volc/v1/contents/generations/tasks "$payload") || die "Failed to create doubao video task"
  task_id=$(extract_task_id "$create_response")
  [[ -n "$task_id" ]] || die "No task id returned from create response: $create_response"

  echo "Task created successfully"
  echo "Task ID: $task_id"
  echo "Model: $model"
  echo "Polling status..." >&2

  poll_response=$(qy_poll GET "/volc/v1/contents/generations/tasks/${task_id}" 10 1800) || die "Doubao video task polling failed"
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
