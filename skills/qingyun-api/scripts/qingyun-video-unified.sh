#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/home/aa/clawd/skills/qingyun-api/scripts/qingyun-common.sh
source "$SCRIPT_DIR/qingyun-common.sh"

usage() {
  cat <<'EOF'
Usage:
  ./qingyun-video-unified.sh "prompt" --model sora-2 [--orientation landscape] [--duration 10] [--images url1,url2] [-o output.mp4]

Description:
  Unified video creation script for QingYun video APIs.
  Supports Sora / Veo / Grok video models via:
    POST /v1/video/create
    GET  /v1/videos/{task_id}

Options:
  --model MODEL           Required. Examples:
                          sora-2, sora-2-pro,
                          grok-video-3,
                          veo3.1-fast, veo3.1-4k, veo3.1-pro-4k, veo3.1-fast-4k
  --orientation MODE      portrait | landscape (mainly for sora)
  --duration SECONDS      Positive integer, e.g. 5 or 10
  --images URLS           Comma-separated image URLs (or references)
  --size SIZE             Sora only: small | large
  --watermark BOOL        Sora only: true | false
  --private BOOL          Sora only: true | false
  --enhance-prompt BOOL   Veo only: true | false
  --aspect-ratio RATIO    Veo/Grok aspect ratio. Examples: 16:9, 9:16, 1:1, 3:2, 2:3
  --enable-upsample BOOL  Veo only: true | false
  -o, --output FILE       Output mp4 path (default: unified-video-YYYYmmdd-HHMMSS.mp4)
  -h, --help              Show this help message

Examples:
  ./qingyun-video-unified.sh "a dog walking in snow" --model sora-2 --orientation landscape --duration 10
  ./qingyun-video-unified.sh "sunset over sea" --model veo3.1-fast --aspect-ratio 16:9 --enhance-prompt true
  ./qingyun-video-unified.sh "cat eating fish" --model grok-video-3 --aspect-ratio 3:2
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

is_bool() {
  case "$1" in
    true|false) return 0 ;;
    *) return 1 ;;
  esac
}

is_sora_model() {
  case "$1" in
    sora-2|sora-2-pro) return 0 ;;
    *) return 1 ;;
  esac
}

is_grok_model() {
  case "$1" in
    grok-video-3) return 0 ;;
    *) return 1 ;;
  esac
}

is_veo_model() {
  case "$1" in
    veo2|veo2-fast|veo2-pro|veo3|veo3-fast|veo3-pro|veo3.1|veo3.1-fast|veo3.1-pro|veo3.1-4k|veo3.1-pro-4k|veo3.1-fast-4k)
      return 0 ;;
    *) return 1 ;;
  esac
}

is_supported_model() {
  is_sora_model "$1" || is_grok_model "$1" || is_veo_model "$1"
}

is_valid_orientation() {
  case "$1" in
    portrait|landscape) return 0 ;;
    *) return 1 ;;
  esac
}

is_valid_size() {
  case "$1" in
    small|large) return 0 ;;
    *) return 1 ;;
  esac
}

is_valid_grok_aspect_ratio() {
  case "$1" in
    2:3|3:2|1:1) return 0 ;;
    *) return 1 ;;
  esac
}

csv_to_json_array() {
  local csv="$1"
  if [[ -z "$csv" ]]; then
    echo '[]'
    return 0
  fi
  printf '%s' "$csv" | jq -Rc 'split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0))'
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
    .data.result_url //
    .data.output_url //
    .result.video_url //
    .result.url //
    .output.video_url //
    .output.url //
    .outputs[0].url //
    .data.outputs[0].url //
    (if (.output | type) == "array" then .output[0] else empty end) //
    empty'
}

main() {
  require_cmd jq
  require_cmd curl
  require_cmd realpath

  local prompt=""
  local model=""
  local orientation=""
  local duration=""
  local images_csv=""
  local size=""
  local watermark=""
  local private_mode=""
  local enhance_prompt=""
  local aspect_ratio=""
  local enable_upsample=""
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
      --orientation)
        shift
        [[ $# -gt 0 ]] || die "--orientation requires a value"
        orientation="$1"
        is_valid_orientation "$orientation" || die "Invalid --orientation: $orientation"
        ;;
      --duration)
        shift
        [[ $# -gt 0 ]] || die "--duration requires a value"
        duration="$1"
        is_positive_int "$duration" || die "--duration must be a positive integer"
        ;;
      --images)
        shift
        [[ $# -gt 0 ]] || die "--images requires a value"
        images_csv="$1"
        ;;
      --size)
        shift
        [[ $# -gt 0 ]] || die "--size requires a value"
        size="$1"
        is_valid_size "$size" || die "Invalid --size: $size"
        ;;
      --watermark)
        shift
        [[ $# -gt 0 ]] || die "--watermark requires a value"
        watermark="$1"
        is_bool "$watermark" || die "--watermark must be true or false"
        ;;
      --private)
        shift
        [[ $# -gt 0 ]] || die "--private requires a value"
        private_mode="$1"
        is_bool "$private_mode" || die "--private must be true or false"
        ;;
      --enhance-prompt)
        shift
        [[ $# -gt 0 ]] || die "--enhance-prompt requires a value"
        enhance_prompt="$1"
        is_bool "$enhance_prompt" || die "--enhance-prompt must be true or false"
        ;;
      --aspect-ratio)
        shift
        [[ $# -gt 0 ]] || die "--aspect-ratio requires a value"
        aspect_ratio="$1"
        ;;
      --enable-upsample)
        shift
        [[ $# -gt 0 ]] || die "--enable-upsample requires a value"
        enable_upsample="$1"
        is_bool "$enable_upsample" || die "--enable-upsample must be true or false"
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

  if is_sora_model "$model"; then
    [[ -z "$enhance_prompt" ]] || die "--enhance-prompt is only supported for veo models"
    [[ -z "$enable_upsample" ]] || die "--enable-upsample is only supported for veo models"
    if [[ -n "$aspect_ratio" ]]; then
      die "--aspect-ratio is not documented for sora models; use --orientation instead"
    fi
  elif is_veo_model "$model"; then
    [[ -z "$orientation" ]] || die "--orientation is only supported for sora models"
    [[ -z "$size" ]] || die "--size is only supported for sora models"
    [[ -z "$watermark" ]] || die "--watermark is only supported for sora models"
    [[ -z "$private_mode" ]] || die "--private is only supported for sora models"
  elif is_grok_model "$model"; then
    [[ -z "$orientation" ]] || die "--orientation is only supported for sora models"
    [[ -z "$duration" ]] || die "--duration is not documented for grok-video-3 unified endpoint"
    [[ -z "$enhance_prompt" ]] || die "--enhance-prompt is only supported for veo models"
    [[ -z "$enable_upsample" ]] || die "--enable-upsample is only supported for veo models"
    [[ -z "$size" ]] || die "--size is only supported for sora models per current docs"
    [[ -z "$watermark" ]] || die "--watermark is only supported for sora models"
    [[ -z "$private_mode" ]] || die "--private is only supported for sora models"
    if [[ -n "$aspect_ratio" ]]; then
      is_valid_grok_aspect_ratio "$aspect_ratio" || die "Grok --aspect-ratio must be one of: 2:3, 3:2, 1:1"
    fi
  fi

  [[ -n "$output" ]] || output="unified-video-$(date +%Y%m%d-%H%M%S).mp4"

  local images_json payload create_response task_id poll_response result_url abs_output
  images_json=$(csv_to_json_array "$images_csv")

  payload=$(jq -n \
    --arg model "$model" \
    --arg prompt "$prompt" \
    --argjson images "$images_json" \
    --arg orientation "$orientation" \
    --arg duration "$duration" \
    --arg size "$size" \
    --arg watermark "$watermark" \
    --arg private_mode "$private_mode" \
    --arg enhance_prompt "$enhance_prompt" \
    --arg aspect_ratio "$aspect_ratio" \
    --arg enable_upsample "$enable_upsample" \
    '
    {
      model: $model,
      prompt: $prompt
    }
    + (if ($images | length) > 0 then {images: $images} else {} end)
    + (if $orientation != "" then {orientation: $orientation} else {} end)
    + (if $duration != "" then {duration: ($duration | tonumber)} else {} end)
    + (if $size != "" then {size: $size} else {} end)
    + (if $watermark != "" then {watermark: ($watermark == "true")} else {} end)
    + (if $private_mode != "" then {private: ($private_mode == "true")} else {} end)
    + (if $enhance_prompt != "" then {enhance_prompt: ($enhance_prompt == "true")} else {} end)
    + (if $aspect_ratio != "" then {aspect_ratio: $aspect_ratio} else {} end)
    + (if $enable_upsample != "" then {enable_upsample: ($enable_upsample == "true")} else {} end)
    ')

  create_response=$(qy_request POST /v1/video/create "$payload") || die "Failed to create unified video task"
  task_id=$(extract_task_id "$create_response")
  [[ -n "$task_id" ]] || die "No task id returned from create response: $create_response"

  echo "Task created successfully"
  echo "Task ID: $task_id"
  echo "Model: $model"
  echo "Polling status..." >&2

  poll_response=$(qy_poll GET "/v1/videos/${task_id}" 10 1800) || die "Unified video task polling failed"
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
