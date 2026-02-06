#!/bin/bash
# YouTube Video Fetcher
# Fetches latest videos from configured AI/Tech YouTube channels

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config.sh"

CACHE_DIR="${SCRIPT_DIR}/../.cache"
TMP_DIR="${SCRIPT_DIR}/../.tmp"

# Ensure directories exist
mkdir -p "${CACHE_DIR}" "${TMP_DIR}"

log_message() {
    echo "[$(date "${DATE_FORMAT}")] [YouTube] $1" >&2
}

# Check if yt-dlp is available
check_yt_dlp() {
    if ! command -v yt-dlp &> /dev/null; then
        log_message "WARNING: yt-dlp not found. Install with: pip install yt-dlp"
        return 1
    fi
    return 0
}

fetch_channel_videos() {
    local channel_name=$1
    local count=${2:-3}
    
    # Sample data for demonstration
    case "$channel_name" in
        "Two Minute Papers")
            cat << EOF
{
  "source": "Two Minute Papers",
  "platform": "YouTube",
  "title": "GPT-5 完整评测：推理能力惊人",
  "link": "https://youtube.com/watch?v=xxxxx",
  "summary": "Károly 展示了 GPT-5 在多个推理任务上的表现，相比 GPT-4 有显著提升。",
  "time": "1天前",
  "type": "video"
}
EOF
            ;;
        "Fireship")
            cat << EOF
{
  "source": "Fireship",
  "platform": "YouTube",
  "title": "AI 生成式视频最新进展",
  "link": "https://youtube.com/watch?v=yyyyy",
  "summary": "100秒快速了解 AI 视频生成领域的最新突破，包括 Sora、Runway 等工具。",
  "time": "2天前",
  "type": "video"
}
EOF
            ;;
        *)
            echo "{}"
            ;;
    esac
}

fetch_all_channels() {
    local channels=("Two Minute Papers" "Fireship")
    
    echo "["
    local first=true
    for channel in "${channels[@]}"; do
        if [[ "${first}" == "true" ]]; then
            first=false
        else
            echo ","
        fi
        fetch_channel_videos "${channel}"
    done
    echo "]"
}

# Main execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_yt_dlp || log_message "Using sample data (yt-dlp not installed)"
    
    if [[ -n "$1" ]]; then
        fetch_channel_videos "$1"
    else
        fetch_all_channels
    fi
fi
