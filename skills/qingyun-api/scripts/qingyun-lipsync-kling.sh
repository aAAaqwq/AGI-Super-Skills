#!/usr/bin/env bash
# qingyun-lipsync-kling.sh — 可灵高级对口型 (Kling Advanced Lip Sync)
# 模型: kling-advanced-lip-sync
# 用法: ./qingyun-lipsync-kling.sh --video URL_OR_BASE64 --audio URL_OR_BASE64 [--start 0] [--end 5000] [-o output.mp4]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/qingyun-common.sh"

# ── 默认值 ──
VIDEO=""
AUDIO=""
SOUND_START_TIME=0
SOUND_END_TIME=5000
SOUND_INSERT_TIME=1000
SOUND_VOLUME=1
ORIGINAL_AUDIO_VOLUME=1
OUTPUT=""
POLL_INTERVAL=10
MAX_WAIT=600

# ── 帮助 ──
show_help() {
  cat <<'EOF'
Usage: qingyun-lipsync-kling.sh --video URL_OR_BASE64 --audio URL_OR_BASE64 [OPTIONS]

可灵高级对口型 — 为视频中的指定人脸匹配音频口型

Required:
  --video URL_OR_BASE64     视频: URL 或 Base64 编码
  --audio URL_OR_BASE64     音频: URL 或 Base64 编码

Options:
  --start MS                音频裁剪起点 (ms) (default: 0)
  --end MS                  音频裁剪终点 (ms) (default: 5000)
  --insert-time MS          音频插入视频的时间点 (ms) (default: 1000)
  --sound-volume NUM        新音频音量 0~2 (default: 1)
  --orig-volume NUM         原始视频音量 0~2 (default: 1)
  -o, --output FILE         输出文件路径 (default: lipsync-output.mp4)
  --poll-interval SEC       轮询间隔秒数 (default: 10)
  --max-wait SEC            最大等待秒数 (default: 600)
  -h, --help                显示帮助

Workflow:
  1. 人脸识别: 上传视频 → 获取 session_id + face_id
  2. 对口型: 传入音频 + face 参数 → 创建对口型任务
  3. 轮询任务 → 下载结果视频

Examples:
  qingyun-lipsync-kling.sh --video https://example.com/video.mp4 --audio https://example.com/speech.mp3
  qingyun-lipsync-kling.sh --video "$(base64 -w0 video.mp4)" --audio "$(base64 -w0 speech.mp3)" -o result.mp4
EOF
}

# ── 参数解析 ──
while [[ $# -gt 0 ]]; do
  case "$1" in
    --video) VIDEO="$2"; shift 2 ;;
    --audio) AUDIO="$2"; shift 2 ;;
    --start) SOUND_START_TIME="$2"; shift 2 ;;
    --end) SOUND_END_TIME="$2"; shift 2 ;;
    --insert-time) SOUND_INSERT_TIME="$2"; shift 2 ;;
    --sound-volume) SOUND_VOLUME="$2"; shift 2 ;;
    --orig-volume) ORIGINAL_AUDIO_VOLUME="$2"; shift 2 ;;
    -o|--output) OUTPUT="$2"; shift 2 ;;
    --poll-interval) POLL_INTERVAL="$2"; shift 2 ;;
    --max-wait) MAX_WAIT="$2"; shift 2 ;;
    -h|--help) show_help; exit 0 ;;
    -*) echo "ERROR: Unknown option: $1" >&2; show_help >&2; exit 1 ;;
    *) shift ;;
  esac
done

# ── 校验 ──
if [[ -z "$VIDEO" ]]; then
  echo "ERROR: --video is required" >&2
  show_help >&2
  exit 1
fi

if [[ -z "$AUDIO" ]]; then
  echo "ERROR: --audio is required" >&2
  show_help >&2
  exit 1
fi

if [[ -z "$OUTPUT" ]]; then
  OUTPUT="lipsync-output.mp4"
fi

# ── Step 1: 人脸识别 ──
echo "=== Step 1: Face Detection ===" >&2

FACE_PAYLOAD=$(jq -n \
  --arg video "$VIDEO" \
  '{video: $video}')

FACE_RESULT=$(qy_request POST "/kling/v1/videos/lip-sync/face" "$FACE_PAYLOAD")

SESSION_ID=$(echo "$FACE_RESULT" | jq -r '.session_id // .data.session_id // empty')
FACE_ID=$(echo "$FACE_RESULT" | jq -r '.face_id // .data.face_id // .face_choose[0].face_id // "-1"')

if [[ -z "$SESSION_ID" || "$SESSION_ID" == "null" ]]; then
  echo "ERROR: Failed to get session_id from face detection" >&2
  echo "$FACE_RESULT" >&2
  exit 1
fi

echo "Face detected — session_id: $SESSION_ID, face_id: $FACE_ID" >&2

# ── Step 2: 创建对口型任务 ──
echo "=== Step 2: Create Lip Sync Task ===" >&2

LIPSYNC_PAYLOAD=$(jq -n \
  --arg session_id "$SESSION_ID" \
  --arg face_id "$FACE_ID" \
  --arg sound_file "$AUDIO" \
  --argjson sound_start_time "$SOUND_START_TIME" \
  --argjson sound_end_time "$SOUND_END_TIME" \
  --argjson sound_insert_time "$SOUND_INSERT_TIME" \
  --argjson sound_volume "$SOUND_VOLUME" \
  --argjson original_audio_volume "$ORIGINAL_AUDIO_VOLUME" \
  '{
    session_id: $session_id,
    face_choose: [{
      face_id: $face_id,
      sound_file: $sound_file,
      sound_start_time: $sound_start_time,
      sound_end_time: $sound_end_time,
      sound_insert_time: $sound_insert_time,
      sound_volume: $sound_volume,
      original_audio_volume: $original_audio_volume
    }]
  }')

LIPSYNC_RESULT=$(qy_request POST "/kling/v1/videos/advanced-lip-sync" "$LIPSYNC_PAYLOAD")

TASK_ID=$(echo "$LIPSYNC_RESULT" | jq -r '.task_id // .data.task_id // .id // empty')
if [[ -z "$TASK_ID" ]]; then
  echo "ERROR: Failed to get task_id from lip sync" >&2
  echo "$LIPSYNC_RESULT" >&2
  exit 1
fi

echo "Lip sync task created: $TASK_ID" >&2

# ── Step 3: 轮询任务 ──
echo "=== Step 3: Polling for result ===" >&2

QUERY_RESULT=$(qy_poll GET "/kling/v1/videos/advanced-lip-sync/$TASK_ID" "$POLL_INTERVAL" "$MAX_WAIT")

# ── 下载视频 ──
VIDEO_URL=$(echo "$QUERY_RESULT" | jq -r '.task_result.video_url // .task_result.videos[0].url // .data.video_url // .data.videos[0].url // .video_url // empty')
if [[ -z "$VIDEO_URL" || "$VIDEO_URL" == "null" ]]; then
  echo "WARNING: No video URL found, raw response:" >&2
  qy_json "$QUERY_RESULT" >&2
  exit 1
fi

qy_download "$VIDEO_URL" "$OUTPUT"
echo "Lip sync complete: $OUTPUT" >&2
