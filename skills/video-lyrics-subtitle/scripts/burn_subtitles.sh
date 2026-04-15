#!/usr/bin/env bash
# burn_subtitles.sh — FFmpeg 烧录字幕到视频
# 自动检测字幕格式（SRT/ASS），调用 FFmpeg 硬字幕烧录
#
# 用法:
#   bash burn_subtitles.sh <video_file> <subtitle_file> [output_file]

set -euo pipefail

# FFmpeg 路径
FFMPEG="${FFMPEG:-$HOME/tools/ffmpeg}"
if ! command -v "$FFMPEG" &>/dev/null; then
    # 回退到系统 ffmpeg
    if command -v ffmpeg &>/dev/null; then
        FFMPEG="$(command -v ffmpeg)"
    else
        echo "❌ 错误：找不到 FFmpeg（尝试 ~/tools/ffmpeg 和系统 PATH）"
        exit 1
    fi
fi

# 参数检查
if [ $# -lt 2 ]; then
    echo "用法: bash burn_subtitles.sh <video_file> <subtitle_file> [output_file]"
    echo ""
    echo "参数:"
    echo "  video_file      输入视频文件"
    echo "  subtitle_file   字幕文件（SRT 或 ASS）"
    echo "  output_file     输出视频文件（可选，默认 <video>_with_subtitles.mp4）"
    echo ""
    echo "环境变量:"
    echo "  FFMPEG          FFmpeg 可执行文件路径（默认 ~/tools/ffmpeg/ffmpeg）"
    exit 1
fi

VIDEO="$1"
SUBTITLE="$2"

# 检查输入文件
if [ ! -f "$VIDEO" ]; then
    echo "❌ 错误：视频文件不存在: $VIDEO"
    exit 1
fi

if [ ! -f "$SUBTITLE" ]; then
    echo "❌ 错误：字幕文件不存在: $SUBTITLE"
    exit 1
fi

# 输出文件
if [ $# -ge 3 ]; then
    OUTPUT="$3"
else
    BASENAME="$(basename "$VIDEO" | sed 's/\.[^.]*$//')"
    DIRNAME="$(dirname "$VIDEO")"
    OUTPUT="${DIRNAME}/${BASENAME}_with_subtitles.mp4"
fi

# 确保输出目录存在
mkdir -p "$(dirname "$OUTPUT")"

# 检测字幕格式
SUB_EXT="${SUBTITLE##*.}"
SUB_EXT_LOWER="$(echo "$SUB_EXT" | tr '[:upper:]' '[:lower:]')"

echo "🎬 烧录字幕到视频"
echo "   视频: $VIDEO"
echo "   字幕: $SUBTITLE ($SUB_EXT_LOWER)"
echo "   输出: $OUTPUT"
echo ""

# FFmpeg 字幕滤镜需要转义特殊字符（路径中的 [] : 等）
# 使用 subtitles= 和 ass= 滤镜
ABS_SUBTITLE="$(cd "$(dirname "$SUBTITLE")" && pwd)/$(basename "$SUBTITLE")"
ESCAPED_SUBTITLE=$(echo "$ABS_SUBTITLE" | sed 's/\\/\\\\/g; s/\:/\\\\:/g; s/\[/\\\\[/g; s/\]/\\\\]/g')

# 根据格式选择滤镜
case "$SUB_EXT_LOWER" in
    srt)
        FILTER="subtitles='${ESCAPED_SUBTITLE}'"
        ;;
    ass)
        FILTER="ass='${ESCAPED_SUBTITLE}'"
        ;;
    *)
        # 默认尝试 subtitles 滤镜（FFmpeg 可自动检测）
        FILTER="subtitles='${ESCAPED_SUBTITLE}'"
        ;;
esac

echo "🔧 FFmpeg 滤镜: $FILTER"
echo ""

# 执行 FFmpeg
set -x
"$FFMPEG" -i "$VIDEO" -vf "$FILTER" -c:a copy -y "$OUTPUT"
set +x

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    FILESIZE=$(du -h "$OUTPUT" | cut -f1)
    echo ""
    echo "✅ 字幕烧录完成!"
    echo "   输出: $OUTPUT ($FILESIZE)"
else
    echo ""
    echo "❌ FFmpeg 烧录失败 (退出码: $EXIT_CODE)"
    exit $EXIT_CODE
fi
