# 5minbtc — BTC 5分钟实时预测 Skill v3.0

> 触发词: `5minbtc`, `5min btc`, `btc 5min`
> 最后更新: 2026-05-06 v3.0 引擎脚本化优化

## 概述

对当前正在进行的5min K线做出方向判断和收盘预测。v3.0 架构：**脚本做指标+方向+预测，LLM只做新闻判断和最终输出**。

## 铁律（不可违反）

1. 每次调用必须重新执行引擎脚本 — 不缓存
2. 每次调用必须重新搜索新闻 — 3组搜索不可省略
3. 必须先 settle 上一根再 log 新预测
4. 输出控制在15行以内（Telegram友好）

## 执行步骤（2步并行 → 1步合成）

### Step 1: 并行启动（4个调用同时发出）

```
并行组:
├── exec: settle-all + 运行引擎脚本（合并为一个命令）
├── web_search: "Bitcoin BTC price news today" count=3
├── web_search: "site:binance.com/en/square BTC Bitcoin" count=3
└── web_search: "比特币 BTC 行情 晚间 最新" count=3
```

**引擎脚本命令**（合并 settle + 计算）：
```bash
cd /home/aa/.openclaw/workspace-cqo && \
  python3 skills/5minbtc/5minbtc-log.py settle-all 2>&1; \
  echo "---ENGINE---"; \
  python3 skills/5minbtc/5minbtc-engine.py 2>&1
```

### Step 2: 合成输出（读取引擎JSON + 新闻摘要）

**LLM只需要做3件事**：
1. 从3组新闻中各提取1-2条关键新闻，标注🟢/🟡/🔴，给出净效应
2. 用新闻净效应微调引擎方向（仅当新闻极强时调整：如重大利空可将bear→strong bear）
3. 填充输出模板

**严格禁止**：LLM不得重新计算指标、不得修改引擎的pred_close/range、不得编造数据。

### Step 3: 记录日志

```bash
python3 skills/5minbtc/5minbtc-log.py log \
  "<engine.candle.iso>" \
  <engine.prediction.pred_close> \
  <engine.prediction.pred_high> \
  <engine.prediction.pred_low> \
  <engine.prediction.confidence> \
  <engine.prediction.bias> \
  <news_sentiment:bull/bear/neutral> \
  <engine.indicators.vol_pct>
```

## 输出模板

```
✅ 验收: [上次K线结算结果，一行]

📈 BTC 5min @ HH:MM | ⏱ XX.X% | $XX,XXX

📰 [2-3条新闻+净效应，4行内]

🧭 [direction] [strength] | EMAΔ±XX ↓/↑ | RSI XX | Vol XX%
[1句技术理由]

🎯 预测: $XX,XXX (开盘$XX,XXX → ±$XX, 📈/📉)
区间: $XX,XXX ~ $XX,XXX
```

**总行数 ≤ 12行**

## 引擎输出格式参考

引擎输出JSON结构（LLM直接读取即可）：
```json
{
  "candle": {"now":"21:25:15","candle_start":"21:25","candle_end":"21:30","progress_pct":5.2,"iso":"..."},
  "price": {"current":81977,"open":81995,"high":81999,"low":81965,"body":-18},
  "indicators": {"ema9":82106,"ema21":82216,"ema_delta":-110.4,"rsi":35.9,"macd":-81.1,"macd_hist":-51.6,"bb_upper":82612,"bb_mid":82267,"bb_lower":81922,"atr":134.8,"vol_pct":6},
  "prediction": {"bias":"bear","strength":"strong","confidence":80,"pred_close":81960,"pred_high":82027,"pred_low":81893}
}
```

## 复盘

```bash
python3 skills/5minbtc/5minbtc-log.py stats
```

## v2→v3 变更

| 项目 | v2 (旧) | v3 (新) |
|------|---------|---------|
| 指标计算 | LLM内联Python | 引擎脚本 (0.5s) |
| 方向判定 | LLM主观判断 | 规则引擎 (deterministic) |
| 收盘预测 | LLM主观预测 | 公式计算+EMA回归 |
| 新闻判断 | LLM | LLM (不可脚本化) |
| 输出格式 | LLM生成 | 模板填充 |
| 总推理时间 | 70-80s | 15-20s |
| Token消耗 | ~30K | ~5-8K |
