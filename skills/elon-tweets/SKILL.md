---
name: elon-tweets
description: Elon Musk tweet market analyzer — pure API, zero browser dependency
---

# 🐦 Elon推文盘猎杀 Skill v2.0

你是Quant。**纯API扫描，零browser依赖**。
核心逻辑：从Gamma赔率分布计算市场隐含预期，与历史发帖速率对比找edge。

## Step 0: 新闻风险检查

```bash
cat ${WORKSPACE}/data/news-risk-level.json 2>/dev/null || echo "{}"
```
- **DANGER**: 🔴 停止，不执行任何交易。
- **CAUTION/NEUTRAL**: 正常执行（Elon盘不直接受加密宏观影响）。

## Step 1: 搜索活跃Elon盘（纯Gamma API，快速预定义slug列表）

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

# 用英文月份名（Polymarket固定用英文）
ET_MONTH=$(LC_ALL=C TZ='America/New_York' date +%B | tr '[:upper:]' '[:lower:]')
NOW_UTC=$(date -u +%Y-%m-%dT%H:%M:%S)

BEST_SLUG=""
BEST_END="9999"
BEST_JSON=""

echo "=== 搜索活跃Elon盘 (month=$ET_MONTH) ==="

# 预定义常见slug模式（2天/7天盘，覆盖最近2周）
for PAIR in "17-24" "20-27" "23-25" "24-26" "24-31" "25-27" "26-28" "27-31"; do
  S=$(echo $PAIR | cut -d- -f1)
  E=$(echo $PAIR | cut -d- -f2)
  SLUG="elon-musk-of-tweets-${ET_MONTH}-${S}-${ET_MONTH}-${E}"
  F="/tmp/elon_slug_${S}_${E}.json"
  curl -s --noproxy '*' --max-time 3 "https://gamma-api.polymarket.com/events?slug=$SLUG" -o "$F"
  C=$(python3 -c "import json;d=json.load(open('$F'));print(len(d))" 2>/dev/null)
  [ "$C" = "0" ] || [ -z "$C" ] && continue
  END_DATE=$(python3 -c "import json;print(json.load(open('$F'))[0].get('endDate',''))" 2>/dev/null)
  if [[ "$END_DATE" > "$NOW_UTC" ]]; then
    echo "  Found: $SLUG | ends: $END_DATE"
    if [[ "$END_DATE" < "$BEST_END" ]]; then
      BEST_END="$END_DATE"
      BEST_SLUG="$SLUG"
      BEST_JSON="$F"
    fi
  fi
done

echo ""
if [ -z "$BEST_SLUG" ]; then
  echo "❌ 无活跃Elon盘"
  exit 0
fi
echo "🎯 目标盘: $BEST_SLUG"
```

无活跃盘→退出不推送。

## Step 2: 纯API分析（无需tweet count）

**用赔率分布计算市场隐含预期，与历史速率对比找edge。零外部依赖。**

```bash
python3 ${WORKSPACE}/scripts/elon_analyze.py "$BEST_JSON"
```

## Step 3: 交易执行（仅<6h且有edge时）

距结算<6h 且 有edge 时：
1. 选择edge最大的区间
2. **必须>3% buffer才入场**（如隐含预期在65-89区间，且YES赔率<45%）
3. 仓位≤可用资产4%，单笔≤$5
4. **不止损，持有到结算**
5. 用browser交易（profile=openclaw）

距结算≥6h 或 无edge → 只记录到daily memory，不交易。

## Step 4: 推送报告

距结算<12h或有交易时才推送，否则静默退出。

```bash
message(action='send', channel='telegram', target='${TELEGRAM_TARGET_ID}', message='报告内容')
```

报告格式：
```
🐦 Elon @ HH:MM
🎯 盘: Mar X-Y | 结算: Xh后
📊 市场隐含预期: XX条
📈 历史投影: 20条/日=XX | 25条/日=XX
⚡ Edge: [描述]
🎯 决策: 买/不买 | 原因
```

## 变更记录
- v2.0 (2026-03-24): **全API重构** — 去除web_fetch/browser依赖，用赔率分布计算隐含预期。修复月份locale bug（LC_ALL=C强制英文）。去tweet count依赖。
- v1.1 (2026-03-17): 修复slug格式bug — Polymarket用`march`不是`mar`
- v1.0 (2026-03-15): 从cron prompt迁移为skill
