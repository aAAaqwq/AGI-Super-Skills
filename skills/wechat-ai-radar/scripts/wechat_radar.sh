#!/bin/bash
# wechat_radar.sh - 微信朋友圈AI雷达快捷命令

set -e

PROJECT_ROOT="$HOME/wechat_ai_radar"
cd "$PROJECT_ROOT"

usage() {
    echo "微信朋友圈AI雷达 - 快捷命令"
    echo ""
    echo "用法: ./wechat_radar.sh <命令> [参数]"
    echo ""
    echo "命令:"
    echo "  briefing      生成日报简报（基于已有数据）"
    echo "  collect       采集朋友圈（滚动截图+AI提取）"
    echo "  full          完整流程（采集+AI提取+简报）"
    echo "  report        生成Word版日报"
    echo "  status        查看数据状态"
    echo "  open          打开微信并激活朋友圈窗口"
    echo ""
    echo "示例:"
    echo "  ./wechat_radar.sh briefing              # 生成日报"
    echo "  ./wechat_radar.sh full                  # 完整采集+简报"
}

case "${1:-}" in
    briefing)
        echo "📋 生成朋友圈日报简报..."
        uv run python reports/generate_daily_report.py
        ;;
    collect)
        echo "📸 采集朋友圈（滚动截图）..."
        uv run python -c "
from automation.open_wechat import WeChatOpener
from automation.scroll_moments import MomentsScroller
opener = WeChatOpener()
opener.activate_wechat()
scroller = MomentsScroller(scroll_count=50, scroll_interval=1.5)
screenshots = scroller.scroll_full(capture=True)
print(f'完成: {len(screenshots)} 张截图')
"
        ;;
    full)
        echo "🚀 完整流程（采集+AI提取+简报）..."
        uv run python run_300.py
        ;;
    report)
        echo "📄 生成Word版日报..."
        uv run python reports/daily_report_to_docx.py
        ;;
    status)
        echo "📊 数据状态:"
        echo ""
        echo "数据库记录数:"
        uv run python -c "
import sys; sys.path.insert(0, '$PROJECT_ROOT')
from db.database import Database
db = Database()
cur = db.conn.execute('SELECT COUNT(*) FROM moments')
print(f'  moments表: {cur.fetchone()[0]} 条')
db.close()
"
        echo ""
        echo "最新截图:"
        ls -t "$PROJECT_ROOT/screenshots/" | head -5 | sed 's/^/  /'
        echo ""
        echo "最新报告:"
        ls -t "$PROJECT_ROOT/reports/"*.md 2>/dev/null | head -3 | sed 's/^/  /'
        echo ""
        echo "最新数据文件:"
        ls -t "$PROJECT_ROOT/data/"extracted_*.json 2>/dev/null | head -3 | sed 's/^/  /'
        ;;
    open)
        echo "💬 打开微信并激活..."
        uv run python -c "
from automation.open_wechat import WeChatOpener
opener = WeChatOpener()
if not opener.is_wechat_running():
    print('启动微信...')
    opener.open_wechat()
else:
    print('微信已在运行')
opener.activate_wechat()
print('微信已激活，请切换到朋友圈窗口')
"
        ;;
    *)
        usage
        ;;
esac