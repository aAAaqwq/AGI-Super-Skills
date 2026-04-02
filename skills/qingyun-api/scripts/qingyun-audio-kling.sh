#!/usr/bin/env bash
# qingyun-audio-kling.sh — 可灵文生音效 (Kling Text-to-Audio)
# 模型: kling-audio
# 用法: ./qingyun-audio-kling.sh "prompt" [--duration 5] [-o output.mp3]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/qingyun-common.sh"

# ── 默认值 ──
PROMPT=""
DURATION="5"
OUTPUT=""
POLL_INTERVAL=10
MAX_WAIT=300

# ── 帮助 ──
show_help() {
  cat <<'EOF'
Usage: qingyun-audio-kling.sh "prompt" [OPTIONS]

可灵文生音效 — 根据文字描述生成音效

Arguments:
  PROMPT                音效描述文本（必填）

Options:
  --duration SECONDS    音频时长，3.0~10.0秒，支持小数 (default: 5)
  -o, --output FILE     输出文件路径 (default: kling-audio-output.mp3)
  --poll-interval SEC   轮询间隔秒数 (default: 10)
  --max-wait SEC        最大等待秒数 (default: 300)
  -h, --help            显示帮助

Examples:
  qingyun-audio-kling.sh "海浪拍打沙滩的声音"
  qingyun-audio-kling.sh "thunder storm" --duration 8 -o storm.mp3
EOF
}

# ── 参数解析 ──
while [[ $# -gt 0 ]]; do
  case "$1" in
    --duration) DURATION="$2"; shift 2 ;;
    -o|--output) OUTPUT="$2"; shift 2 ;;
    --poll-interval) POLL_INTERVAL="$2"; shift 2 ;;
    --max-wait) MAX_WAIT="$2"; shift 2 ;;
    -h|--help) show_help; exit 0 ;;
    -*) echo "ERROR: Unknown option: $1" >&2; show_help >&2; exit 1 ;;
    *) PROMPT="$1"; shift ;;
  esac
done

# ── 校验 ──
if [[ -z "$PROMPT" ]]; then
  echo "ERROR: Prompt is required" >&2
  show_help >&2
  exit 1
fi

# 校验 duration: 3.0 ~ 10.0
if ! awk "BEGIN { exit !($DURATION >= 3.0 && $DURATION <= 10.0) }"; then
  echo "ERROR: Duration must be between 3.0 and 10.0, got: $DURATION" >&2
  exit 1
fi

if [[ -z "$OUTPUT" ]]; then
  OUTPUT="kling-audio-output.mp3"
fi

# ── 创建任务 ──
echo "Kling Audio — prompt: ${PROMPT:0:80} duration: ${DURATION}s" >&2

PAYLOAD=$(jq -n \
  --arg prompt "$PROMPT" \
  --arg duration "$DURATION" \
  '{prompt: $prompt, duration: $duration}')

CREATE_RESULT=$(qy_request POST "/kling/v1/audio/text-to-audio" "$PAYLOAD")

TASK_ID=$(echo "$CREATE_RESULT" | jq -r '.task_id // .data.task_id // .id // empty')
if [[ -z "$TASK_ID" ]]; then
  echo "ERROR: Failed to get task_id from response" >&2
  echo "$CREATE_RESULT" >&2
  exit 1
fi

echo "Task created: $TASK_ID" >&2

# ── 轮询任务 ──
QUERY_RESULT=$(qy_poll GET "/kling/v1/audio/text-to-audio/$TASK_ID" "$POLL_INTERVAL" "$MAX_WAIT")

# ── 下载音频 ──
AUDIO_URL=$(echo "$QUERY_RESULT" | jq -r '.task_result.video_url // .task_result.audio_url // .data.video_url // .data.audio_url // .video_url // .audio_url // empty')
if [[ -z "$AUDIO_URL" || "$AUDIO_URL" == "null" ]]; then
  echo "WARNING: No audio URL found, raw response:" >&2
  qy_json "$QUERY_RESULT" >&2
  exit 1
fi

qy_download "$AUDIO_URL" "$OUTPUT"
