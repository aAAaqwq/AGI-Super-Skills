#!/bin/bash
# BTC 5-Min Signal Scanner v2.0
# 用法: bash scan_signals.sh [--json]
# 扫描Binance 1m K线，输出时段自适应信号

set -euo pipefail
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY 2>/dev/null || true

JSON_MODE=false
[[ "${1:-}" == "--json" ]] && JSON_MODE=true

echo "=== BTC 5-Min Signal Scanner v2.0 ==="
echo "时间: $(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S CST') / $(date -u '+%H:%M UTC')"
echo ""

# 获取K线数据
DATA=$(curl -s --max-time 10 "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=30")

if [ -z "$DATA" ] || [ "$DATA" = "[]" ]; then
    echo "❌ 数据获取失败"
    exit 1
fi

# 获取当前UTC小时 (去掉前导零)
UTC_HOUR=$(date -u +%H | sed 's/^0//')
UTC_HOUR=${UTC_HOUR:-0}

# 时段判断函数
get_session() {
    local hour=$1
    if [[ $hour -ge 13 && $hour -lt 14 ]]; then
        echo "DANGER"
    elif [[ $hour -ge 3 && $hour -lt 7 ]]; then
        echo "ASIAN_MOMENTUM"
    elif [[ $hour -ge 15 && $hour -lt 18 ]]; then
        echo "US_REVERSION"
    else
        echo "NEUTRAL"
    fi
}

SESSION=$(get_session "$UTC_HOUR")

# 时段系数
case $SESSION in
    ASIAN_MOMENTUM) SESSION_MULT=1.2 ;;
    US_REVERSION) SESSION_MULT=0.6 ;;
    NEUTRAL) SESSION_MULT=0.5 ;;
    DANGER) SESSION_MULT=0 ;;
    *) SESSION_MULT=0.5 ;;
esac

# 分析信号
RESULT=$(echo "$DATA" | jq --arg session "$SESSION" --argjson session_mult "$SESSION_MULT" -r '
  # 解析K线
  [.[] | {
    open: (.[1] | tonumber),
    close: (.[4] | tonumber),
    high: (.[2] | tonumber),
    low: (.[3] | tonumber),
    vol: (.[5] | tonumber),
    change: ((.[4] | tonumber) - (.[1] | tonumber))
  }] as $candles |
  
  $candles[-1].close as $price |
  
  # EMA计算 (SMA近似)
  ([$candles[-9:][] | .close] | add / 9) as $ema9 |
  ([$candles[-21:][] | .close] | add / 21) as $ema21 |
  (if $ema9 > $ema21 then "UP" elif $ema9 < $ema21 then "DOWN" else "FLAT" end) as $ema_dir |
  
  # RSI近似 (价格位置)
  ($candles[-1].close - ([$candles[] | .low] | min)) as $up_range |
  (([$candles[] | .high] | max) - $candles[-1].close) as $dn_range |
  (100 * $up_range / (if ($up_range + $dn_range) > 0 then ($up_range + $dn_range) else 1 end)) as $rsi_approx |
  (if $rsi_approx < 30 then "OVERSOLD" elif $rsi_approx > 70 then "OVERBOUGHT" else "NEUTRAL" end) as $rsi_status |
  
  # 5分钟数据
  [$candles[-5:][] | .change] as $last5 |
  ($last5 | add) as $mom5 |
  (([$candles[-5:][] | .high] | max) - ([$candles[-5:][] | .low] | min)) as $range5 |
  
  # S1: 动量延续 (连续2个同向)
  [$candles[-2:][] | if .change > 0 then 1 elif .change < 0 then -1 else 0 end] as $dirs2 |
  (if ($dirs2 | add) == 2 then "UP" elif ($dirs2 | add) == -2 then "DOWN" else "NONE" end) as $s1_momentum |
  
  # S2: EMA趋势
  (if $ema_dir == "UP" then "UP" elif $ema_dir == "DOWN" then "DOWN" else "NONE" end) as $s2_ema |
  
  # S3: RSI极值
  (if $rsi_status == "OVERSOLD" then "UP" elif $rsi_status == "OVERBOUGHT" then "DOWN" else "NONE" end) as $s3_rsi |
  
  # S4: 均值回归 (仅美盘)
  (if $session == "US_REVERSION" and $mom5 > 200 then "DOWN"
   elif $session == "US_REVERSION" and $mom5 < -200 then "UP"
   else "NONE" end) as $s4_reversion |
  
  # 信号计数
  (if $session == "ASIAN_MOMENTUM" then
    [[$s1_momentum, $s2_ema, $s3_rsi] | .[] | select(. == "UP")] | length
  elif $session == "US_REVERSION" then
    [[$s4_reversion, $s3_rsi, $s2_ema] | .[] | select(. == "UP")] | length
  else 0 end) as $up_signals |
  
  (if $session == "ASIAN_MOMENTUM" then
    [[$s1_momentum, $s2_ema, $s3_rsi] | .[] | select(. == "DOWN")] | length
  elif $session == "US_REVERSION" then
    [[$s4_reversion, $s3_rsi, $s2_ema] | .[] | select(. == "DOWN")] | length
  else 0 end) as $dn_signals |
  
  # Kelly仓位 (简化: 55%胜率, 0.48买入价 = 9%半Kelly)
  (if ($up_signals >= 2 or $dn_signals >= 2) then
    ((100 * 0.09 * $session_mult) | if . > 5 then 5 else . end)
  else 0 end) as $position |
  
  # 综合判断
  (if $session == "DANGER" then "🚫 SKIP - 危险时段"
   elif $up_signals >= 2 then "🟢 ENTER UP"
   elif $dn_signals >= 2 then "🔴 ENTER DOWN"
   elif $up_signals == 1 or $dn_signals == 1 then "⚪ SKIP - 仅1信号"
   else "⚪ SKIP - 无信号" end) as $verdict |
  
  # 输出JSON
  {
    price: $price,
    session: $session,
    session_mult: $session_mult,
    ema9: $ema9,
    ema21: $ema21,
    ema_dir: $ema_dir,
    rsi_approx: $rsi_approx,
    rsi_status: $rsi_status,
    mom5: $mom5,
    range5: $range5,
    s1_momentum: $s1_momentum,
    s2_ema: $s2_ema,
    s3_rsi: $s3_rsi,
    s4_reversion: $s4_reversion,
    up_signals: $up_signals,
    dn_signals: $dn_signals,
    position: $position,
    verdict: $verdict
  }
')

if $JSON_MODE; then
    echo "$RESULT" | jq .
else
    echo "📊 时段: $SESSION (x${SESSION_MULT})"
    echo "$RESULT" | jq -r '
    "BTC: $\(.price)",
    "EMA9/21: \(.ema9 | . * 100 | round / 100) / \(.ema21 | . * 100 | round / 100) → \(.ema_dir)",
    "RSI: \(.rsi_approx | . * 10 | round / 10) → \(.rsi_status)",
    "5min: 波幅 $\(.range5 | round) | 动量 $\(.mom5 | round)",
    "",
    "信号:",
    "  S1动量: \(.s1_momentum) \(if .s1_momentum != "NONE" then "✅" else "❌" end)",
    "  S2 EMA: \(.s2_ema) \(if .s2_ema != "NONE" then "✅" else "❌" end)",
    "  S3 RSI: \(.s3_rsi) \(if .s3_rsi != "NONE" then "✅" else "❌" end)",
    "",
    "UP: \(.up_signals) | DOWN: \(.dn_signals) | 仓位: $\(.position | . * 100 | round / 100)",
    "",
    ">>> \(.verdict)"
    '
fi
