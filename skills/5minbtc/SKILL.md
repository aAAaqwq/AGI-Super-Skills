# 5minbtc — BTC 5分钟实时预测 Skill v3.1

> 触发词: `5minbtc`, `5min btc`, `btc 5min`
> 最后更新: 2026-05-06 v3.1 引擎提供数据+基准，LLM做完整分析

## 概述

对当前5min K线做方向判断和收盘预测。v3.1架构：**引擎脚本算指标+给基准建议，LLM做综合分析+微调+完整输出**。

## 铁律

1. 每次必须重新执行引擎脚本 — 不缓存
2. 每次必须重新搜索3组新闻
3. 先 settle 上一根，再 log 新预测
4. LLM可微调引擎的bias/pred_close/range，但必须说明理由
5. 输出15-25行（平衡深度和Telegram可读性）

## 执行步骤

### Step 1: 并行启动（4个调用同时发出）

```
并行组:
├── exec: settle-all + 引擎脚本（合并一条命令）
├── web_search: "Bitcoin BTC breaking news price" count=3 freshness=day
├── web_search: "crypto market macro stocks today" count=3 freshness=day
└── web_search: "比特币 BTC 最新 晚间" count=3 freshness=day
```

引擎输出已包含FnG(恐惧贪婪指数)，无需额外API调用。

引擎命令：
```bash
cd /home/aa/.openclaw/workspace-cqo && \
  python3 skills/5minbtc/5minbtc-log.py settle-all 2>&1; \
  echo "---ENGINE---"; \
  python3 skills/5minbtc/5minbtc-engine.py 2>&1
```

### Step 2: LLM完整分析（参考引擎数据，不是机械填模板）

LLM收到引擎JSON后，必须：

**A. 验收上一根K线**（从settle输出）
- 显示：K线时间、预测 vs 实际、误差、方向✅/❌、区间✅/❌
- 1句偏差复盘

**B. 综合判断方向**（引擎给基准，LLM最终决定）
- 引擎的bias/strength是**参考起点**，不是最终答案
- LLM必须考虑引擎忽略的因素：
  - 超卖/超买后的反转概率（RSI<30不一定是继续跌）
  - BB下轨/上轨的支撑/阻力效应
  - 连续阴/阳线后的疲劳（5连阴后反弹概率上升）
  - K线形态（十字星、锤子线、吞没等）
  - 新闻方向的权重调整
- 如果LLM调整了引擎方向，必须说明理由

**C. 微调预测价**（引擎给基准，LLM微调±ATR*0.3以内）
- 引擎pred_close是数学基准
- LLM可基于K线形态、新闻、超卖反弹等调整
- 调整幅度不超过ATR*0.3

**D. 完整输出**（包含技术分析逻辑，不是只列数字）

### Step 3: 记录日志

```bash
python3 skills/5minbtc/5minbtc-log.py log \
  "<engine.candle.iso>" \
  <final_pred_close> \
  <final_pred_high> \
  <final_pred_low> \
  <confidence> \
  <final_bias> \
  <news_sentiment> \
  <engine.indicators.vol_pct>
```

## 输出模板

```
✅ 验收: [上次K线时间] pred=$XX,XXX actual=$XX,XXX err=±$XX (±X.XX%) dir✅/❌ rng✅/❌
[1句复盘]

📈 BTC 5min 实时预测 @ HH:MM:SS
当前K线: HH:MM→HH:MM | ⏱ XX.X% (剩XmXs)
实时价: $XX,XXX | O=XX,XXX H=XX,XXX L=XX,XXX C=XX,XXX (body ±$XX)
---
📰 今日关键新闻:
- 🟢 [新闻1] — 影响
- 🟡 [新闻2] — 影响
- 🔴 [新闻3] — 影响
新闻净效应: 🟢/🟡/🔴 [原因]

🧭 方向: 📈/📉 [bull/bear] [strong/medium/weak] | 依据: [2-3个关键指标+新闻]
- 引擎基准: [engine bias/strength] → LLM调整: [如有调整写理由，无则写"确认引擎判断"]
- EMA9=$XX,XXX / EMA21=$XX,XXX (Δ±$XX)
- RSI=XX.X [超买/超卖/中性]
- MACD=XX.X / Signal=XX.X (Hist=XX.X)
- BB: $XX,XXX / $XX,XXX / $XX,XXX [价格位置]
- ATR=$XX.X | Vol=XX% of avg [放量/缩量/正常]

[2-3句核心分析：结合技术+新闻+K线形态的综合判断]

---
🎯 收盘预测:
| 情景 | 目标区间 | 概率 |
|------|---------|------|
| [主要情景] | $XX,XXX-$XX,XXX | XX% ← |
| [次要情景] | $XX,XXX-$XX,XXX | XX% |

**开盘$XX,XXX → 预测$XX,XXX** (±$XX, ±X.XX%) → 📈/📉

> [1句关键备注]
```

## 引擎JSON结构（LLM直接读取）

```json
{
  "candle": {"now":"21:36:49","candle_start":"21:35","candle_end":"21:40","progress_pct":36.6,"iso":"..."},
  "price": {"current":81995,"open":82004,"high":82025,"low":81949,"body":-9},
  "recent_candles": [{"O":82023,"H":82089,"L":81965,"C":81995},...],
  "indicators": {
    "ema9":82064.1, "ema21":82176.6, "ema_delta":-112.4,
    "rsi":38.1, "macd":-91.49, "macd_signal":-51.46, "macd_hist":-40.04,
    "bb_upper":82541.9, "bb_mid":82211.6, "bb_lower":81881.3,
    "atr":142.0, "vol_pct":26.0
  },
  "momentum": {"consecutive_bull":1, "consecutive_bear":0},
  "prediction": {"bias":"bear","strength":"strong","confidence":80,"score":-72,
                 "pred_close":81970,"pred_high":82041,"pred_low":81899}
}
```

## 复盘

```bash
python3 skills/5minbtc/5minbtc-log.py stats
```

## v2→v3.1 变更

| 项目 | v2 | v3 (过度精简) | v3.1 (当前) |
|------|-----|-------------|------------|
| 指标计算 | LLM内联 | 引擎脚本 | 引擎脚本 |
| 方向判定 | LLM主观 | 引擎规则 | **引擎基准+LLM最终判定** |
| 收盘预测 | LLM主观 | 引擎公式 | **引擎基准+LLM微调** |
| 新闻判断 | LLM | LLM | LLM |
| 输出深度 | 完整 | 过简 | **完整** |
| MACD修复 | ❌ (signal=0) | ✅ | ✅ |
| 推理耗时 | 70-80s | 15-20s | **25-40s** |
| Token消耗 | ~30K | ~5K | **~10-12K** |
