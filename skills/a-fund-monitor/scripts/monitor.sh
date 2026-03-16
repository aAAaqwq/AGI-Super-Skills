#!/bin/bash
# A股基金监控 - 通用版
# 数据源：天天基金（东方财富旗下）
# 用法：bash monitor.sh [--push] [--codes "代码1 代码2"]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

# 清代理（减少网络波动）
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

# 读取配置
CONFIG_FILE="$SKILL_DIR/config.json"
HOLIDAYS_FILE="$SKILL_DIR/holidays.txt"

# 时间变量
NOW=$(date '+%H:%M')
TODAY=$(date '+%Y-%m-%d')
DOW=$(date '+%u')  # 1=周一, 7=周日
HOUR=$(date '+%-H')

# 判断是否在盘中（9:00 - 15:00）
IS_TRADING=0
if [ $HOUR -ge 9 ] && [ $HOUR -lt 15 ]; then
  IS_TRADING=1
fi

# 判断是否是周末（用数字比较）
IS_WEEKEND=0
if [ "$DOW" -eq 6 ] || [ "$DOW" -eq 7 ]; then
  IS_WEEKEND=1
fi

# 检查今天是否是节假日
IS_HOLIDAY=0
if [ -f "$HOLIDAYS_FILE" ]; then
  while IFS= read -r h; do
    [ -z "$h" ] && continue
    [ "$TODAY" = "$h" ] && IS_HOLIDAY=1 && break
  done < "$HOLIDAYS_FILE"
fi

# 是否是非交易日
IS_NON_TRADING_DAY=0
if [ $IS_WEEKEND -eq 1 ] || [ $IS_HOLIDAY -eq 1 ]; then
  IS_NON_TRADING_DAY=1
fi

# 解析命令行参数
PUSH_MODE="none"  # none, full, force, brief
CUSTOM_CODES=""

while [ $# -gt 0 ]; do
  case "$1" in
    --push)
      PUSH_MODE="full"
      shift
      ;;
    --force)
      PUSH_MODE="force"
      shift
      ;;
    --brief)
      PUSH_MODE="brief"
      shift
      ;;
    --codes)
      CUSTOM_CODES="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# 获取要监控的基金代码
if [ -n "$CUSTOM_CODES" ]; then
  CODES="$CUSTOM_CODES"
else
  # 从配置文件读取
  if [ -f "$CONFIG_FILE" ] && command -v jq &>/dev/null; then
    CODES=$(jq -r '.funds[].code' "$CONFIG_FILE" 2>/dev/null | tr '\n' ' ')
  fi
  # 如果没有配置或读取失败，使用默认配置
  if [ -z "$CODES" ]; then
    CODES="000979 002943 003304 015790 015508 006479 519771 014418 012414 025209 000217 012768"
  fi
fi

# 从配置文件获取基金名称
declare -A NAMES
if [ -f "$CONFIG_FILE" ] && command -v jq &>/dev/null; then
  while IFS= read -r line; do
    code=$(echo "$line" | jq -r '.code')
    name=$(echo "$line" | jq -r '.name')
    [ -n "$code" ] && [ -n "$name" ] && NAMES[$code]="$name"
  done < <(jq -c '.funds[]' "$CONFIG_FILE" 2>/dev/null)
fi

# 默认名称（配置文件中没有的）
NAMES[003304]="前海开源沪港深核心资源混合A"
NAMES[015790]="永赢高端装备智选混合发起C"
NAMES[015508]="兴业中证500指数增强C"
NAMES[000979]="景顺长城沪港深精选股票A"
NAMES[006479]="广发纳斯达克100ETF联接人民币"
NAMES[519771]="交银优择回报灵活配置混合C"
NAMES[014418]="西部利得CES芯片指数增强A"
NAMES[012414]="招商中证白酒指数(LOF)C"
NAMES[002943]="广发多因子混合"
NAMES[025209]="永赢先锋半导体智选混合发起C"
NAMES[000217]="华安黄金ETF联接C"
NAMES[012768]="华夏中证动漫游戏ETF发起式联接"

# 带重试的curl函数
fetch_with_retry() {
  local url="$1"
  local referer="$2"
  local result=""
  for i in 1 2; do
    result=$(curl -s -m 3 -H "Referer: $referer" "$url" 2>/dev/null)
    if [ -n "$result" ]; then
      echo "$result"
      return 0
    fi
    [ $i -eq 1 ] && sleep 0.5
  done
  return 1
}

# 生成报告
REPORT="📊 A股基金监控 [$NOW]\n━━━━━━━━━━━━━━"
SUM=0
COUNT=0
TOTAL=0

for code in $CODES; do
  TOTAL=$((TOTAL + 1))
  name="${NAMES[$code]:-$code}"
  
  if [ $IS_TRADING -eq 1 ]; then
    # 盘中：优先用实时估值接口
    est=$(fetch_with_retry "http://fundgz.1234567.com.cn/js/${code}.js" "https://fund.eastmoney.com/")
    gsz=$(echo "$est" | grep -oP '"gsz":"[^"]*"' | cut -d'"' -f4)
    gszzl=$(echo "$est" | grep -oP '"gszzl":"[^"]*"' | cut -d'"' -f4)
    gztime=$(echo "$est" | grep -oP '"gztime":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$gszzl" ]; then
      sign=""
      [ "$(echo "$gszzl > 0" 2>/dev/null | bc)" = "1" ] && sign="+"
      icon=""
      abs_val=$(echo "$gszzl" | tr -d '-')
      [ "$(echo "$abs_val > 3" 2>/dev/null | bc)" = "1" ] && icon=" 🔥"
      REPORT="$REPORT\n${name} | ${gsz} | ${sign}${gszzl}%${icon} ⚡${gztime}"
      SUM=$(echo "$SUM + $gszzl" | bc 2>/dev/null)
      COUNT=$((COUNT + 1))
    else
      # 回退到历史净值
      raw=$(fetch_with_retry "http://api.fund.eastmoney.com/f10/lsjz?callback=j&fundCode=${code}&pageIndex=1&pageSize=1&startDate=&endDate=" "http://fundf10.eastmoney.com/")
      nav=$(echo "$raw" | grep -oP '"DWJZ":"[^"]*"' | head -1 | cut -d'"' -f4)
      chg=$(echo "$raw" | grep -oP '"JZZZL":"[^"]*"' | head -1 | cut -d'"' -f4)
      nav_date=$(echo "$raw" | grep -oP '"FSRQ":"[^"]*"' | head -1 | cut -d'"' -f4)
      if [ -n "$nav" ] && [ -n "$chg" ]; then
        sign=""
        [ "$(echo "$chg > 0" 2>/dev/null | bc)" = "1" ] && sign="+"
        REPORT="$REPORT\n${name} | ${nav} | ${sign}${chg}% ($nav_date)"
        SUM=$(echo "$SUM + $chg" | bc 2>/dev/null)
        COUNT=$((COUNT + 1))
      fi
    fi
  else
    # 盘后：用实际净值
    raw=$(fetch_with_retry "http://api.fund.eastmoney.com/f10/lsjz?callback=j&fundCode=${code}&pageIndex=1&pageSize=1&startDate=&endDate=" "http://fundf10.eastmoney.com/")
    nav=$(echo "$raw" | grep -oP '"DWJZ":"[^"]*"' | head -1 | cut -d'"' -f4)
    chg=$(echo "$raw" | grep -oP '"JZZZL":"[^"]*"' | head -1 | cut -d'"' -f4)
    nav_date=$(echo "$raw" | grep -oP '"FSRQ":"[^"]*"' | head -1 | cut -d'"' -f4)
    
    if [ -n "$nav" ] && [ -n "$chg" ]; then
      # 日期标记
      date_note=""
      if [ "$nav_date" != "$TODAY" ]; then
        date_note=" ($nav_date)"
      fi
      
      sign=""
      [ "$(echo "$chg > 0" 2>/dev/null | bc)" = "1" ] && sign="+"
      icon=""
      abs_val=$(echo "$chg" | tr -d '-')
      [ "$(echo "$abs_val > 3" 2>/dev/null | bc)" = "1" ] && icon=" 🔥"
      REPORT="$REPORT\n${name} | ${nav} | ${sign}${chg}%${icon}${date_note}"
      SUM=$(echo "$SUM + $chg" | bc 2>/dev/null)
      COUNT=$((COUNT + 1))
    fi
  fi
done

# 计算平均值
AVG="0.00"
if [ "$COUNT" -gt 0 ]; then
  AVG=$(printf "%.2f" $(echo "scale=4; $SUM / $COUNT" | bc 2>/dev/null))
fi

# 生成报告尾部
if [ "$COUNT" -gt 0 ]; then
  if [ $IS_TRADING -eq 1 ]; then
    REPORT="$REPORT\n━━━━━━━━━━━━━━\n📈 平均涨跌: ${AVG}% | 监控: ${COUNT}/${TOTAL}\n📌 数据: 东方财富实时估值"
  else
    REPORT="$REPORT\n━━━━━━━━━━━━━━\n📈 平均涨跌: ${AVG}% | 监控: ${COUNT}/${TOTAL}\n📌 数据: 东方财富实际净值"
  fi
else
  REPORT="$REPORT\n⚠️ 获取失败"
fi

# 输出到控制台
echo -e "$REPORT"

# 调试输出
echo "DEBUG: PUSH_MODE=$PUSH_MODE, IS_WEEKEND=$IS_WEEKEND, IS_NON_TRADING_DAY=$IS_NON_TRADING_DAY" >&2

# 推送逻辑
# --push: 交易日推送完整报告，非交易日推送简短提示
# --force: 强制推送完整报告（无论是否交易日）
if [ "$PUSH_MODE" = "full" ] || [ "$PUSH_MODE" = "force" ]; then
  if [ $IS_NON_TRADING_DAY -eq 1 ] && [ "$PUSH_MODE" != "force" ]; then
    # 非交易日且不是强制推送：推送简短提示
    if [ $IS_WEEKEND -eq 1 ]; then
      reason="周末休市"
    else
      reason="节假日休市"
    fi
    BRIEF="📊 A股基金监控 [$NOW]\n━━━━━━━━━━━━━━\n🌙 今日${reason}\n📈 最近净值: ${AVG}%\n📌 ${COUNT}/${TOTAL} 只基金"
    python3 ~/clawd/scripts/newsbot_send.py "$(echo -e "$BRIEF")"
  else
    # 交易日 或 强制推送完整报告
    python3 ~/clawd/scripts/newsbot_send.py "$(echo -e "$REPORT")"
  fi
elif [ "$PUSH_MODE" = "brief" ]; then
  # 明确要求简短提示
  if [ $IS_WEEKEND -eq 1 ]; then
    reason="周末休市"
  else
    reason="节假日休市"
  fi
  BRIEF="📊 A股基金监控 [$NOW]\n━━━━━━━━━━━━━━\n🌙 今日${reason}\n📈 最近净值: ${AVG}%\n📌 ${COUNT}/${TOTAL} 只基金"
  python3 ~/clawd/scripts/newsbot_send.py "$(echo -e "$BRIEF")"
fi
