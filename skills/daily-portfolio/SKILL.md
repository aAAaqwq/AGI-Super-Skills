# 📊 每日持仓盘点 Skill

你是Quant。早间全量盘点，输出持仓日报。

## 脚本目录

```
skills/daily-portfolio/scripts/
└── poly_positions.py    # Polymarket持仓+余额查询
```

## Step 1: 清代理 + 价格
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
curl -s --max-time 10 'https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT'
curl -s --max-time 10 'https://data-api.binance.vision/api/v3/ticker/price?symbol=ETHUSDT'
```

## Step 2: 读取策略和记忆
- memory/昨天.md + memory/今天.md
- SOUL.md 血泪教训

## Step 3: 获取Polymarket持仓

```bash
python3 "$SKILL_DIR/scripts/poly_positions.py"
```

输出：USDC余额、总资产、每个活跃持仓详情、可Claim仓位。

## Step 4: API失败Fallback
- API失败 → 用 Gamma API 获取价格
- 仍失败 → browser 备用（profile=openclaw）

## Step 5: 推送日报
```
message(action='send', channel='telegram', target='YOUR_TELEGRAM_CHAT_ID', message='报告内容')
```

格式：
```
📊 Quant 持仓日报 [MM-DD HH:MM]
━━━━━━━━━━━━━━
💰 Portfolio: $XX | Cash: $XX
📈 BTC: $XX,XXX | ETH: $X,XXX

• BTC>$74k NO 买入85¢ → 现价90¢ (+6%)
⚠️ 需操作: {止损/止盈建议}
📌 数据源: {CLOB API / fallback}
```

## Step 6: 更新 memory/今天.md
