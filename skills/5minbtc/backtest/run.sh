#!/usr/bin/env bash
# 5minbtc Backtest Runner — 一键运行完整回测
#
# 用法:
#   ./run.sh                  # 下载最新数据 + 完整回测
#   ./run.sh --fast           # 快速回测 (每小时采样, 最近180天)
#   ./run.sh --sample 6       # 每30分钟采样
#   ./run.sh --days 90        # 只回测最近90天
#   ./run.sh --full-report    # 完整因子分析报告
#   ./run.sh --skip-fetch     # 跳过数据下载, 直接回测

set -euo pipefail
cd "$(dirname "$0")"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  📊 5minbtc Engine v5.6 — Backtest Runner${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""

SKIP_FETCH=false
EXTRA_ARGS=""

for arg in "$@"; do
    case $arg in
        --skip-fetch) SKIP_FETCH=true ;;
        --fast) EXTRA_ARGS="$EXTRA_ARGS --fast" ;;
        --full-report) EXTRA_ARGS="$EXTRA_ARGS --full-report" ;;
        --sample=*) EXTRA_ARGS="$EXTRA_ARGS $arg" ;;
        --days=*) EXTRA_ARGS="$EXTRA_ARGS $arg" ;;
        --force) EXTRA_ARGS="$EXTRA_ARGS --force" ;;
    esac
done

# Step 1: 数据下载
if [ "$SKIP_FETCH" = false ]; then
    echo -e "${YELLOW}📡 Step 1: 下载/更新K线数据${NC}"
    python3 fetch_data.py
    echo ""
else
    echo -e "${YELLOW}📡 Step 1: 跳过数据下载 (--skip-fetch)${NC}"
    if [ ! -f "data/btcusdt_5m.json" ]; then
        echo -e "${RED}❌ 数据文件不存在, 请先运行不带 --skip-fetch 的命令${NC}"
        exit 1
    fi
fi

# Step 2: 数据检查
echo -e "${YELLOW}📂 Step 2: 验证数据${NC}"
python3 -c "
import json, os
if not os.path.exists('data/btcusdt_5m.json'):
    print('❌ 数据文件不存在')
    exit(1)
with open('data/btcusdt_5m.json') as f:
    data = json.load(f)
import time
days = (data[-1]['ct'] - data[0]['ot']) / (24*3600*1000)
print(f'✅ {len(data):,} 根K线, {days:.0f} 天覆盖')
if days < 30:
    print('⚠️  数据不足30天, 建议重新下载')
"
echo ""

# Step 3: 运行回测
echo -e "${YELLOW}🔄 Step 3: 运行回测${NC}"
python3 run_backtest.py $EXTRA_ARGS

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ 回测完成!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo "结果文件:"
ls -lh results/ 2>/dev/null || echo "  (无结果文件)"
