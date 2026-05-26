---
name: 5minbtc
version: 5.5
description: BTC 5分钟K线实时方向预测。v5.5校准置信度引擎，9正交因子+Platt Scaling+Regime感知+Bull惩罚+中性区收缩。基于120轮v5.4实战复盘优化。
triggers:
  - 5minbtc
  - 5min btc
  - btc 5min
tools:
  - terminal
  - web
---

# 5minbtc — BTC 5分钟实时预测 v5.5

> 最后更新: 2026-05-26 v5.5校准置信度引擎

## v5.5 变更 (2026-05-26)

基于120轮v5.4实战复盘的4项优化：

| 优先级 | 修复项 | 变更 | 影响 |
|--------|--------|------|------|
| P0-1 | 置信度校准 | `40+abs(score)` → Platt Scaling sigmoid | conf与准确率正相关 |
| P0-2 | 新闻因子 | 98% NEUTRAL死代码，保留扫描给LLM | 减少噪声 |
| P1-1 | Bull bias | score>0时×0.92衰减 | bear 70.2% > bull 65.4%修正 |
| P1-2 | 高vol惩罚 | HIGH_VOL 0.6→0.45 | 放量准确率更低 |

附加优化：
- neutral区收缩 [-2,2]→[-1,1]，减少无信息预测
- 置信度上限 80→85，让强信号有区分度
- `calibrate_confidence()` 独立函数，midpoint=15, steepness=0.10

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

v5.4输出示例：
```json
{
  "candle": {"now":"21:36:49","candle_start":"21:35","candle_end":"21:40","progress_pct":36.6,"iso":"..."},
  "price": {"current":75502,"open":75498,"high":75520,"low":75480,"body":4},
  "recent_candles": [{"O":75498,"H":75520,"L":75480,"C":75502},...],
  "indicators": {
    "ema9":75490.1, "ema21":75510.6, "ema_delta":-20.5,
    "rsi":48.2, "macd":-12.3, "macd_signal":-8.1, "macd_hist":-4.2,
    "bb_upper":75600, "bb_mid":75480, "bb_lower":75360,
    "atr":85.0, "vol_pct":45.0
  },
  "momentum": {"consecutive_bull":1, "consecutive_bear":0},
  "regime": "TREND",
  "factors": {
    "momentum_tstat": -0.09, "zscore_meanrev": -0.05, "rsi_momentum": +0.21,
    "volume_condition": 0.0, "fatigue": 0.0,
    "momentum_deceleration": +1.00, "price_position": -0.09,
    "imbalance": null, "microprice": null
  },
  "prediction": {"bias":"neutral","strength":"weak","confidence":41,"score":1,
                 "pred_close":75502,"pred_high":75567,"pred_low":75437}
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
| v5.4 | 正交因子+Regime | 68.1%(120r) | 9正交因子+sigmoid+TREND dampening+meanrev反转 |
| **v5.5** | **+校准置信度** | **待验证** | **Platt Scaling+Bull惩罚+高vol增强+neutral区收缩** |

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
- `references/quant-knowledge-index.md` — 50轮蒸馏知识库索引(14份报告/~80KB)，含升级优先级

## 报告库

14份深度蒸馏报告存放在 `reports/` 目录（也同步在 AGI-Super-Team 仓库）：
- R01-R12：50轮蒸馏（因子理论、策略、DeFi、组合、ML、数据源、前沿研究、期权、微结构、风控、机构方法论、整合蓝图）
- R13：准确率优化方案（178笔复盘后）
- R14：引擎审计报告（顶尖量化审查，4个Critical修复→v5.0架构设计基础）

## 仓库同步

Skill已同步至 AGI-Super-Team 仓库 `skills/5minbtc/`：
- 仓库路径: `~/clawd/repos/AGI-Super-Team/skills/5minbtc/`
- 包含: 引擎、日志模块、新闻模块、SKILL.md、reports/、references/
- 不包含: `data/` 目录（运行时数据）、`5minbtc-log.jsonl`（实时预测记录，按需同步）
- 同步命令: `cp` 核心文件 → `git add` → `git commit` → `git push origin master`
