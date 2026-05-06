# 5minbtc — BTC 5分钟实时预测 Skill v2.2

> 触发词: `5minbtc`, `5min btc`, `btc 5min`
> 最后更新: 2026-05-05 v2.2 并行优化

## 概述

对当前正在进行的5min K线做出**方向判断**和**收盘预测**，结合技术指标+最新新闻，给出方向信号、概率分布和具体收盘目标价。

## 铁律（不可违反）

1. **每次调用必须重新获取数据** — 不缓存，不偷懒，不复制上轮结果
2. **每次调用必须重新搜索新闻** — 市场瞬息万变，5分钟前的新闻可能已过时
3. **同一根K线多次请求也要重新完整分析** — 价格在变，评估也要变
4. **必须记录每笔预测到日志** — 调用 `5minbtc-log.py log`
5. **上一根K线结束后必须结算** — 调用 `5minbtc-log.py settle`

## 执行步骤（每次调用都必须全部执行）

### Step 1: 并行启动（settle + API + 3组新闻 同时发出）

⚠️ **所有以下调用必须在同一个 function_calls block 中并行发出，不得串行！**

```
并行组:
├── exec: settle上根K线
├── exec: 获取当前K线进度（精确到秒）
├── exec: curl Binance API 获取22根K线 + 计算指标
├── web_search: 英文主流 "Bitcoin BTC news today"
├── web_search: Binance Square "site:binance.com/en/square Bitcoin BTC"
└── web_search: 中文圈 "币安广场 Bitcoin BTC 最新消息"
```

### Step 2: 汇总分析（等并行组全部返回后）

从 Binance API (`api.binance.me`) 获取最近100根5min K线，计算：

| 指标 | 公式 | 用途 |
|------|------|------|
| EMA9/EMA21 | 标准EMA | 趋势方向+金叉/死叉 |
| RSI(14) | Wilder RSI | 超买超卖 |
| MACD | EMA12-EMA26 | 动能方向 |
| Bollinger Bands | SMA20±2σ | 波动区间+位置 |
| ATR(14) | 真实波幅均值 | 预期波动范围 |
| Volume vs avg20 | 当前量/均值 | 量能确认 |

**必须输出**:
- 当前K线实时: O/H/L/C/body
- 最近3根已完成K线: O/H/L/C

### Step 3: 获取最新新闻（必须重新搜索，多源）

用 `web_search` 搜索以下3组（每组 count=3-5）：
1. `Bitcoin BTC news today May 2026` — 英文主流源
2. `site:binance.com/en/square Bitcoin BTC news` — 币安广场
3. `币安广场 Bitcoin BTC 最新消息 暴跌` — 中文圈

**三组都必须搜**，不同语言/社区的视角经常互补甚至矛盾，这是重要信号。

对每条新闻标注：
- 🟢 利多 / 🟡 中性偏多 / ⚪ 中性 / 🔴 利空
- **必须给出新闻净效应**总结
- **必须将新闻影响融入预测判断**（不能只列新闻不结合）

### Step 4: 记录预测

```bash
python3 skills/5minbtc/5minbtc-log.py log \
  "<candle_start_iso>" <pred_close> <pred_high> <pred_low> \
  <confidence> <bias:bull/bear/neutral> <news:bull/bear/neutral> <vol_pct>
```

### Step 5: 方向判断（必须每次明确输出）

基于技术+新闻给出明确方向信号：

```
方向: 📈 多头 / 📉 空头 / ➡️ 震荡
强度: 强(>70%) / 中(50-70%) / 弱(<50%)
信号来源: EMA趋势 + MACD动能 + RSI区间 + 新闻净效应 + V型反弹验证
```

**方向判断规则**：
1. MACD > 0 + EMA9 > EMA21 = 基础多头
2. MACD > 50 + EMAΔ > 50 = 强多头（不预测深度回调）
3. MACD < 0 + EMA9 < EMA21 = 基础空头
4. MACD < -50 + EMAΔ < -50 = 强空头
5. 当天V型反弹验证 ≥ 2次 → 信任回调即买入，方向偏多
6. 新闻净效应 = bull/bear/neutral → 加权调整方向

**输出格式**（每次必须包含）：
```
🧭 方向: 📈 强多头 (MACD+135, EMAΔ+132, V型×5, 新闻🟢)
```

### Step 6: 预测当前K线收盘

## 预测规则（基于复盘经验）

### 强趋势判断
```
if MACD > 50 AND EMA9-EMA21 > 50:
    → 强多头，不预测冲高回落
    → BB上轨不作为阻力（强趋势中BB上轨是目标不是天花板）
    → 预测bias = bull
    → 只预测"温和整理"或"继续走高"
```

### V型反弹信任
```
if 当天已验证 >= 2次 EMA9 V型反弹后创新高:
    → 信任回调即买入模式
    → 不预测深度回调
    → 回调预测幅度减半
```

### 区间宽度
```
pred_range = ±ATR * 0.5（不能低于±ATR*0.3）
# 之前用±$20-30太窄，导致33%命中率
# ATR约$80-90时，range应±$40-50
```

### 冲高回落评估
```
# 最大教训：不要看到冲高就预测回落
# 必须结合：
1. MACD是否仍然强势（>50 = 不预测深度回落）
2. 量能是否放大（放大 = 获利了结可能大）
3. 新闻是否支持继续走高
4. 当天V型反弹次数（>=2 = 信任多头）
```

## 输出模板

```
📈 BTC 5min 实时预测 @ HH:MM:SS

当前K线: HH:MM → HH:MM | ⏱ XX.X% (剩余XmXs)
实时价: $XX,XXX | K线内 OXXXXX HXXXXX LXXXXX CXXXXX

---

📰 今日关键新闻:
- 🟢 新闻标题 — 影响
- 🟡 新闻标题 — 影响
新闻净效应: 🟢/🟡/🔴 原因

🧭 方向: 📈绿UP / 📉红DOWN (收盘 vs 开盘) | 强/中/弱 | 依据: MACD, EMAΔ, V型×N, 新闻

---

🎯 当前K线 (HH:MM-HH:MM) 收盘预测:

[2-3句技术分析 + 新闻结合的核心判断]

| 收盘情景 | 目标区间 | 概率 |
|---------|---------|------|
| 情景A | $xx,xxx-$xx,xxx | xx% ← |
| 情景B | $xx,xxx-$xx,xxx | xx% |
| 情景C | $xx,xxx-$xx,xxx | xx% |

**开盘 vs 预测收盘**: $XX,XXX → $XX,XXX (**+$XX / -XX.XX%**) → 📈绿UP / 📉红DOWN

预测收盘: $XX,XXX（一句话理由）

> 关键备注
```

## 约束

- 不预测下一根K线，只预测**当前这根**
- 进度<10%时提示"K线刚开始，预测可靠性低"
- 进度>80%时给出更高置信度
- **新闻每次必须重新搜索，绝不缓存** ⚠️
- **技术数据每次必须重新从API获取** ⚠️
- **同一根K线被多次请求也要重新完整执行所有步骤** ⚠️
- 输出控制在15行以内（Telegram友好）
- 不给交易建议（除非用户主动问）

## 复盘日志

每次session结束或用户要求时，运行复盘：
```bash
python3 skills/5minbtc/5minbtc-log.py stats
```

复盘报告写入 `skills/5minbtc/review-YYYY-MM-DD.md`

### Day 1 (2026-05-05) 复盘摘要
- 19笔预测：方向58%，区间37%，MAE 0.064%
- 震荡期(09:10-09:45)优秀：方向78%
- 突破期(09:50-10:30)崩溃：方向40%
- 核心问题：冲高回落恐惧+BB上轨迷信+区间太窄
- 详见 `review-2026-05-05.md`
