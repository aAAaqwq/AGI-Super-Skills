# 5minbtc — BTC 5分钟实时预测 Skill v3.2

> 触发词: `5minbtc`, `5min btc`, `btc 5min`
> 最后更新: 2026-05-12 v3.3 新闻源精简：移除失效源，Cointelegraph TG(3min)+CoinDesk RSS(14min)+TreeNews(120min)

## 概述

对当前5min K线做方向判断和收盘预测。v3.1架构：**引擎脚本算指标+给基准建议，LLM做综合分析+微调+完整输出**。

## 铁律

1. 每次必须重新执行引擎脚本 — 不缓存
2. 每次必须重新搜索3组新闻
3. 先 settle 上一根，再 log 新预测
4. LLM可微调引擎的bias/pred_close/range，但必须说明理由
5. 输出15-25行（平衡深度和Telegram可读性）

## 执行步骤

### Step 1: 并行启动（5个调用同时发出）

```
并行组:
├── exec: settle-all + 引擎脚本（合并一条命令）
├── exec: 5minbtc-news.py（新闻扫描，更新news-risk-level.json）
├── web_search: "Bitcoin BTC breaking news price" count=3 freshness=day
├── web_search: "crypto market macro stocks today" count=3 freshness=day
└── web_search: "比特币 BTC 最新 晚间" count=3 freshness=day
```

引擎输出已包含FnG(恐惧贪婪指数)，无需额外API调用。

引擎命令：
```bash
cd <workspace> && \
  python3 skills/5minbtc/5minbtc-log.py settle-all 2>&1; \
  echo "---ENGINE---"; \
  python3 skills/5minbtc/5minbtc-engine.py 2>&1; \
  echo "---NEWS---"; \
  python3 skills/5minbtc/5minbtc-news.py 2>&1
```

新闻扫描会自动更新 `data/news-risk-level.json`（结构化情绪+风险等级），供Step 2使用。

### Step 2: LLM完整分析（参考引擎数据，不是机械填模板）

LLM收到引擎JSON后，必须：

**A. 验收上一根K线**（从settle输出）
- 显示：K线时间、预测 vs 实际、误差、方向✅/❌、区间✅/❌
- 1句偏差复盘

**B. 综合判断方向**（引擎给基准，LLM最终决定）
- 引擎的bias/strength是**参考起点**，不是最终答案
- 读取 `data/news-risk-level.json` 获取结构化新闻情绪（sentiment, risk_level）
- LLM必须考虑引擎忽略的因素：
  - 超卖/超买后的反转概率（RSI<30不一定是继续跌）
  - BB下轨/上轨的支撑/阻力效应
  - 连续阴/阳线后的疲劳（5连阴后反弹概率上升）
  - K线形态（十字星、锤子线、吞没等）
  - 新闻方向的权重调整（HIGH_VOL→降低信心，LOW_RISK→可提高信心）
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
📰 今日关键新闻 [结构化信号: 🟢BULLISH/🟡NEUTRAL/🔴BEARISH | 风险: LOW_RISK/NORMAL/ELEVATED/HIGH_VOL]:
- 🟢 [新闻1] — 影响
- 🟡 [新闻2] — 影响
- 🔴 [新闻3] — 影响
新闻净效应: 🟢/🟡/🔴 [原因] | 结构化: [news-risk-level.json sentiment]

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

## 新闻数据源 (5minbtc-news.py)

新闻脚本：`skills/5minbtc/5minbtc-news.py`
输出文件：`data/news-risk-level.json`（供引擎读取）

| 源 | 延迟 | 状态 |
|-----|------|------|
| **Cointelegraph** | **~3min** | ✅ Telegram TG频道，实时推送 |
| **CoinDesk** | **~14min** | ✅ RSS实时 |
| **TreeNews** | ~120min | ⚠️ Telegram群，依赖tree_channel编辑推送频率 |
| CoinTelegraph RSS | 144min+ | ❌ 已移除（延迟过高） |
| NewsData.io | 20h+ | ❌ 已移除（数据完全失效） |
| TheBlock | blocked | ❌ 已移除（SSL封锁） |
| BitcoinMagazine | blocked | ❌ 已移除（连接重置） |
| Fear&Greed | blocked | ❌ 已移除（连接重置） |
| CryptoCompare | 需key | ❌ 已移除（无API key） |

**Keys**（已写入 `~/.bashrc`）:
- `COINDESK_API_KEY=<your-coindesk-key>`
- `NEWSDATA_API_KEY=<your-newsdata-key>`

风险判定规则:
- bearish ≥ 2 → BEARISH + HIGH_VOL
- bullish ≥ 2 → BULLISH + LOW_RISK
- bearish = 1 → NEUTRAL + ELEVATED
- 其他 → NEUTRAL + NORMAL

## 引擎进化史 & 复盘记录

### 版本演进

| 版本 | 架构 | 方向准确率 | 关键变更 |
|------|------|-----------|----------|
| v3.1 | 线性打分(EMA+RSI+MACD+Vol) | 64% | 基础版，引擎+LLM混合 |
| v3.2 | +量价背离/动量衰竭/VWAP | — | Alpha101借鉴，+16行 |
| v3.3 | +RSS/Binance新闻 | — | 新闻数据源接入 |
| v3.4 | +OB/Funding/鲸鱼 | — | 实时微结构(后被证明噪声) |
| v3.5 | **概率框架重写** | 75% | 8因子→log-odds→贝叶斯概率 |
| v3.5.1 | +低vol衰减/VWAP因子 | 77% | 当前版本 |
| v3.2 | +结构化新闻扫描 | — | 5minbtc-news.py集成，news-risk-level.json供引擎读取 |

### 全量复盘 (141笔结算)

| 日期 | 笔数 | 方向 | 区间 | MAE | 特征 |
|------|------|------|------|-----|------|
| 05-05 | 107 | 64% | 55% | 0.071% | v3.1，大量测试，bull偏多 |
| 05-06 | 28 | 57% | 71% | 0.068% | v3.1，bear偏多，区间最好 |
| 05-11 | 8+ | 83% | 83% | 0.042% | v3.1手动，最佳表现 |
| 05-12 | 27 | 74% | 56% | 0.038% | v3.5.1 cron运行 |

**全局**: 方向 64% | 区间 60% | MAE 0.069%

### 核心教训

1. **线性打分是初学者错误** — 多个共线指标叠加不增加信息量
2. **64%方向准确率接近随机** — 应专注区间覆盖而非方向预测
3. **引擎越自信越错(v3.4)** — 极端信号出现在行情末端=反转概率最高(v3.5已修复)
4. **低vol微波动不应判方向** — ≤0.05%波动是噪声(v3.5.1衰减至0.3)
5. **EMA在底部反弹期天然滞后** — 导致连续判DOWN(VWAP因子部分修复)

### 因子有效性 (148笔验证)

| ✅ 有效 | ❌ 无效/噪声 |
|---------|-------------|
| EMA delta (弱) | RSI (5min 40-60无信号) |
| Vol pct (辅助) | MACD (与EMA共线) |
| 量价背离 (理论有效) | OB失衡 (快照噪声) |
| VWAP (抵消EMA滞后) | Funding (8h结算无关5min) |
| 动量衰竭 (趋势末端) | 鲸鱼大单 (0.05BTC门槛太低) |
| — | RSS情绪 (148笔贡献为0) |

### v3.5 概率框架要点

- 8个独立因子 → log-odds → 贝叶斯概率 P(UP/DOWN/NEUTRAL)
- Regime detection: ranging(低vol衰减0.3) / transitional / trending
- 区间设计: ranging=0.45ATR, trending=0.35ATR
- 砍掉: RSI, MACD, RSS, 高权重OB/Funding
- 确信度vs准确率: 60-69%最稳(80%), 90%+命中(100%)
- UP判断88%准确, DOWN判断65%(瓶颈)

### 下一步优化方向

1. RSI超卖反弹因子 (RSI<30→UP +0.5, 抵消EMA滞后)
2. 低可信度标签 (regime=ranging+vol<25%→标注⚠️)
3. 区间加宽至0.50 ATR (56%太低)

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
