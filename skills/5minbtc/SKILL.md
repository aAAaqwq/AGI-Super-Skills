---
name: 5minbtc
version: 5.4
description: BTC 5分钟K线实时方向预测。v5.4正交因子+Regime感知+微结构引擎，9因子（momentum t-stat/Z-score meanrev/RSI/volume/fatigue/decel/position/imbalance/microprice），sigmoid压缩，TREND dampening。
triggers:
  - 5minbtc
  - 5min btc
  - btc 5min
tools:
  - terminal
  - web
---

# 5minbtc — BTC 5分钟实时预测 v4.0

> 最后更新: 2026-05-22 Hermes迁移版

## 概述

对当前5min K线做方向判断和收盘预测。架构：**引擎脚本算指标+给基准建议，LLM做综合分析+微调+完整输出**。

## 铁律

1. 每次必须重新执行引擎脚本 — 不缓存
2. 每次必须重新搜索3组新闻
3. 先 settle 上一根，再 log 新预测
4. LLM可微调引擎的bias/pred_close/range，但必须说明理由
5. 输出15-25行（平衡深度和Telegram可读性）

## ⚠️ Pitfalls

### Binance API 451 封禁
中国大陆所有标准 Binance 端点返回 HTTP 451。必须用 `data-api.binance.vision` 替代 `api.binance.com` / `api.binance.me`。
详见 `references/binance-api-geo.md`。
验证: `curl -s -o /dev/null -w "%{http_code}" "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=5"` → 200

### 路径硬编码
不要用 `WORKSPACE = dirname(dirname(dirname(...)))` 指向旧 OpenClaw workspace。用 `SKILL_DIR = os.path.dirname(os.path.abspath(__file__))`。

## 执行步骤

### Step 1: 并行启动（5个调用同时发出）

```
并行组:
├── exec: settle-all + 引擎脚本 + 新闻扫描（合并一条命令）
├── web_search: "Bitcoin BTC breaking news price" count=3 freshness=day
├── web_search: "crypto market macro stocks today" count=3 freshness=day
└── web_search: "比特币 BTC 最新 晚间" count=3 freshness=day
```

引擎命令（绝对路径）：
```bash
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc && \
  python3 $SKILL_DIR/5minbtc-log.py settle-all 2>&1; \
  echo "---ENGINE---"; \
  python3 $SKILL_DIR/5minbtc-engine-v5.py 2>&1; \
  echo "---NEWS---"; \
  python3 $SKILL_DIR/5minbtc-news.py 2>&1
```

新闻扫描会自动更新 `data/news-risk-level.json`（结构化情绪+风险等级），供Step 2使用。

### Step 2: LLM完整分析（参考引擎数据，不是机械填模板）

LLM收到引擎JSON后，必须：

**A. 验收上一根K线**（从settle输出）
- 显示：K线时间、预测 vs 实际、误差、方向✅/❌、区间✅/❌
- 1句偏差复盘

**B. 综合判断方向**（引擎给基准，LLM最终决定）
- 引擎的bias/strength是**参考起点**，不是最终答案
- 读取 `data/news-risk-level.json` 获取结构化新闻情绪
- LLM必须考虑引擎忽略的因素：
  - 超卖/超买后的反转概率
  - BB下轨/上轨的支撑/阻力效应
  - 连续阴/阳线后的疲劳
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
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc && \
  python3 $SKILL_DIR/5minbtc-log.py log \
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
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc && \
  python3 $SKILL_DIR/5minbtc-log.py stats
```

## 新闻数据源

| 源 | 延迟 | 状态 |
|-----|------|------|
| **CoinDesk** | **~14min** | ✅ RSS实时 |
| **Cointelegraph** | **~3min** | ⚠️ 需TG脚本（已降级为RSS fallback） |
| **TreeNews** | ~120min | ⚠️ 需TG脚本（已降级） |

## 引擎进化史 & 复盘记录

### 版本演进

| 版本 | 架构 | 方向准确率 | 关键变更 |
|------|------|-----------|----------|
| v3.1 | 线性打分(EMA+RSI+MACD+Vol) | 64% | 基础版，引擎+LLM混合 |
| v3.5.1 | +低vol衰减/VWAP因子 | 77% | 最佳版本 |
| v4.0 | Hermes迁移 | 60.5% | 路径适配，功能不变 |
| v4.1 | Phase1修复 | 目标70%+ | 过度自信压制+放量反转+bull修正+疲劳增强 |
| **v5.4** | **正交因子+Regime** | **60.7%(50r)** | **9正交因子+sigmoid+TREND dampening+meanrev反转** |

### 全量复盘 (178笔结算)

| 日期 | 笔数 | 方向 | 区间 | MAE | 特征 |
|------|------|------|------|-----|------|
| 05-05 | 107 | 64% | 55% | 0.071% | v3.1，大量测试 |
| 05-06 | 28 | 57% | 71% | 0.068% | v3.1，区间最好 |
| 05-11 | 8+ | 83% | 83% | 0.042% | v3.1手动，最佳表现 |
| 05-12 | 27 | 74% | 56% | 0.038% | v3.5.1 cron运行 |
| 05-23 | — | — | — | — | v4.1上线，待验证 |

**全局(v4.0)**: 方向 60.5% | 区间 62.1% | MAE 0.064%

### 核心教训

1. **过度自信是最致命问题** — conf≥60准确率56.8% < conf<60的65.4%，极端信号=行情末端
2. **放量≠确认方向，放量=反转预警** — 放量(≥80%)准确率仅50%
3. **bull偏向严重** — bull准确率57.3% < bear 63.4%，引擎过度解读EMA金叉
4. **线性打分是初学者错误** — 多个共线指标叠加不增加信息量
5. **低vol微波动准确率最高** — 缩量时66%，应专注而非放弃
6. **EMA在底部反弹期天然滞后** — VWAP因子部分修复

## v5.0 升级路线图

> 详见 `references/quant-knowledge-index.md` 和 `~/.hermes/profiles/cqo/quant-knowledge/R12-integration-blueprint.md`

### P0 — 立即实施
1. **OFI微结构因子**: Binance WebSocket → 订单流不平衡 → 预测R²~15-25%
2. **免费数据源**: Arkham(鲸鱼), Binance WS(LOB), Deribit(IV)
3. **信号仪表板**: 监控因子IC/衰减率 (Simons哲学)

### P1 — 2-4周
4. Regime-aware仓位 (HMM检测)
5. LightGBM自动化因子筛选
6. CVaR动态止损

### P2 — 1-2月
7. TFT多时间尺度模型 → 替代贝叶斯引擎
8. 期权IV信号 (Deribit)
9. 完整压力测试框架

### 关键数学升级
- OFI (Cont et al. 2014) → 替代纯价格指标
- Microprice (Stoikov 2018) → 替代 mid price
- Kalman滤波 → 动态EMA权重
- HMM Regime → 自适应仓位
- GPD尾部 → 替代固定止损

## 参考文件

- `references/binance-api-geo.md` — Binance API 区域封禁解决方案和迁移记录
- `references/quant-knowledge-index.md` — 50轮蒸馏知识库索引(12份报告/~67KB)，含升级优先级
