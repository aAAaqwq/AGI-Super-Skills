#!/usr/bin/env bash
# Binance Square Scraper — Chrome CDP 启动器
# 功能：
#   1. 检测 Chrome CDP 是否已在 9222 端口运行
#   2. 若无，自动启动 Chrome（User Profile + Remote Debugging）
#   3. 运行 scraper
#   4. 可选：结束后关闭 Chrome（--keep-alive 时保留）
#
# 用法：
#   ./run_with_chrome.sh --min 60 --topics 5 --per-topic 20
#   ./run_with_chrome.sh --min 60 --topics 0          # 只爬广场
#   ./run_with_chrome.sh --keep-alive --min 60        # 保留 Chrome 进程
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHROME_PORT=9222
CHROME_HOST=localhost
CHROME_URL="http://${CHROME_HOST}:${CHROME_PORT}"
PROFILE_DIR="${HOME}/.config/google-chrome/Default"
KEEP_ALIVE=false

# ---------- 解析参数 ----------
while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-alive)  KEEP_ALIVE=true; shift ;;
        --port)         CHROME_PORT="$2"; shift 2 ;;
        *)              SCRAPER_ARGS+=("$1"); shift ;;
    esac
done

# ---------- 检查 Chrome CDP 是否运行 ----------
check_chrome() {
    curl -s --max-time 3 "${CHROME_URL}/json" > /dev/null 2>&1
}

# ---------- 启动 Chrome ----------
start_chrome() {
    echo "🔍 Chrome CDP 未运行，正在启动..."

    # 检查 Chrome 是否已安装
    if ! command -v google-chrome &> /dev/null; then
        echo "❌ google-chrome 未找到，请先安装 Chrome"
        exit 1
    fi

    # 检查 Profile 目录
    if [[ ! -d "$PROFILE_DIR" ]]; then
        echo "❌ Chrome Profile 目录不存在: $PROFILE_DIR"
        exit 1
    fi

    # 启动 Chrome（远程调试模式）
    nohup google-chrome \
        --user-data-dir="$PROFILE_DIR" \
        --remote-debugging-port="$CHROME_PORT" \
        --no-sandbox \
        --disable-dev-shm-usage \
        --headless=new \
        --new-window \
        "https://www.binance.com/zh-CN/square" \
        > /tmp/chrome_cdp.log 2>&1 &

    CHROME_PID=$!
    echo "✅ Chrome 已启动 (PID: $CHROME_PID, Port: $CHROME_PORT)"

    # 等待 Chrome 就绪（最多 15s）
    for i in $(seq 1 15); do
        if check_chrome; then
            echo "✅ Chrome CDP 就绪 (${i}s)"
            return 0
        fi
        sleep 1
    done

    echo "❌ Chrome CDP 启动超时"
    return 1
}

# ---------- 主流程 ----------
echo "=========================================="
echo "Binance Square Scraper — Chrome CDP Launcher"
echo "=========================================="

if check_chrome; then
    echo "✅ Chrome CDP 已运行 (Port: $CHROME_PORT)，复用已有会话"
else
    start_chrome
fi

# 设置 CDP URL 环境变量（供 scraper 使用）
export CDP_CHROME_PORT="$CHROME_PORT"
export CDP_CHROME_HOST="$CHROME_HOST"

# 运行 scraper
echo ""
echo "📥 运行 Scraper..."
cd "$SCRIPT_DIR"
python3 square_scraper_cdp.py "${SCRAPER_ARGS[@]}"

# 清理
if [[ "$KEEP_ALIVE" == "false" ]]; then
    echo ""
    echo "🧹 关闭 Chrome CDP..."
    pkill -f "remote-debugging-port=$CHROME_PORT" 2>/dev/null || true
    echo "✅ Chrome 已关闭"
else
    echo ""
    echo "🔵 Chrome 继续运行 (Port: $CHROME_PORT)"
    echo "   后续运行可省略重新启动步骤"
fi

echo ""
echo "=========================================="
echo "Done"
