---
name: daily-portfolio
description: Morning portfolio review — full position snapshot and daily P&L report
---

# 📊 每日持仓盘点 Skill

你是Quant。早间全量盘点，输出持仓日报。

## Step 1: 清代理 + Binance价格
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
curl -s --max-time 10 'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT'
curl -s --max-time 10 'https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT'
curl -s --max-time 10 'https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT'
```

## Step 2: 读取策略和记忆
- memory/昨天.md + memory/今天.md
- SOUL.md血泪教训
- data/strategy-v4.md

## Step 3: 获取Polymarket持仓（API优先）

```bash
# 余额 + 可用资金
python3 skills/polymarket-api/scripts/poly_trade.py balance

# 完整持仓快照（含盈亏、已结算、可Claim）
python3 scripts/api_position_monitor.py
```

从API输出提取:
- Portfolio总值、Cash余额
- 每个仓位: 市场名称、方向、买入价、现价、盈亏%
- 可Claim的已结算仓位

## Step 4: API失败时的Browser Fallback
- API全部失败 → 用browser备用: `browser(action='navigate', profile='openclaw', targetUrl='https://polymarket.com/portfolio')`
- 看到登录页 → 推送告警: "⚠️ Polymarket登录态丢失，需人工刷新"
- 用Gamma API备用获取价格

## Step 5: 推送日报
```bash
message(action='send', channel='telegram', target='${TELEGRAM_TARGET_ID}', message='报告内容')
```

格式(纯文本，适配Telegram):
```
📊 Quant 持仓日报 [MM-DD HH:MM]
━━━━━━━━━━━━━━
💰 Portfolio: $XX | Cash: $XX
📈 BTC: $XX,XXX | ETH: $X,XXX | SOL: $XX

• BTC>$74k Mar16 NO
  买入85¢ → 现价90¢ (+6%)

• Fed不变Apr YES
  买入86¢ → 现价89¢ (+3%)

⚠️ 需操作: {止损/止盈建议}
📌 数据源: {CLOB API / browser fallback}
```

## Step 6: 更新memory/今天.md

## Step 7: 浏览器清理
```bash
pkill -f 'chrome.*remote-debugging-port=18800' 2>/dev/null
```

## 变更记录
- v1.0 (2026-03-15): 从cron prompt迁移为skill
