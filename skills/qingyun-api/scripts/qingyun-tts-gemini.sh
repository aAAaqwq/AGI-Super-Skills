#!/usr/bin/env bash
# qingyun-tts-gemini.sh — Gemini TTS (文生语音)
# 模型: gemini-2.5-flash-preview-tts, gemini-2.5-pro-preview-tts
# 用法: ./qingyun-tts-gemini.sh "要说的文本" [--model MODEL] [--voice VOICE] [-o OUTPUT]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/qingyun-common.sh"

# ── 默认值 ──
MODEL="gemini-2.5-flash-preview-tts"
VOICE="Kore"
OUTPUT=""
TEXT=""

# ── 帮助 ──
show_help() {
  cat <<'EOF'
Usage: qingyun-tts-gemini.sh "要说的文本" [OPTIONS]

Gemini TTS — 将文本转为语音文件

Arguments:
  TEXT                  要转换为语音的文本（必填）

Options:
  --model MODEL         模型选择 (default: gemini-2.5-flash-preview-tts)
                        - gemini-2.5-flash-preview-tts  (快速)
                        - gemini-2.5-pro-preview-tts    (高品质)
  --voice VOICE         语音名称 (default: Kore)
                        常见: Kore, Charon, Puck, Fenrir, Aoede, Leda, Orus, Zephyr
  -o, --output FILE     输出文件路径 (default: tts-output.mp3)
  -h, --help            显示帮助

Examples:
  qingyun-tts-gemini.sh "你好，世界"
  qingyun-tts-gemini.sh "Hello world" --model gemini-2.5-pro-preview-tts --voice Fenrir -o hello.mp3
EOF
}

# ── 参数解析 ──
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --voice) VOICE="$2"; shift 2 ;;
    -o|--output) OUTPUT="$2"; shift 2 ;;
    -h|--help) show_help; exit 0 ;;
    -*) echo "ERROR: Unknown option: $1" >&2; show_help >&2; exit 1 ;;
    *) TEXT="$1"; shift ;;
  esac
done

# ── 校验 ──
if [[ -z "$TEXT" ]]; then
  echo "ERROR: Text is required" >&2
  show_help >&2
  exit 1
fi

if [[ "$MODEL" != "gemini-2.5-flash-preview-tts" && "$MODEL" != "gemini-2.5-pro-preview-tts" ]]; then
  echo "ERROR: Invalid model '$MODEL'. Choose: gemini-2.5-flash-preview-tts, gemini-2.5-pro-preview-tts" >&2
  exit 1
fi

if [[ -z "$OUTPUT" ]]; then
  OUTPUT="tts-output.mp3"
fi

# ── 构造请求 ──
echo "Gemini TTS — model=$MODEL voice=$VOICE" >&2
echo "Text: ${TEXT:0:80}..." >&2

PAYLOAD=$(jq -n \
  --arg text "$TEXT" \
  --arg voice "$VOICE" \
  '{
    contents: [{parts: [{text: $text}]}],
    generationConfig: {
      responseModalities: ["AUDIO"],
      speechConfig: {
        voiceConfig: {
          prebuiltVoiceConfig: {voiceName: $voice}
        }
      }
    }
  }')

# ── 调用 API ──
PATH_API="/v1beta/models/${MODEL}:generateContent"
RESULT=$(qy_gemini "$PATH_API" "$PAYLOAD")

# ── 保存音频 ──
qy_save_gemini_audio "$RESULT" "$OUTPUT"
