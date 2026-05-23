# R13: 5minbtc 方向准确率优化方案

> 基于177笔结算数据的深度复盘 + 50轮蒸馏知识的交叉验证
> 目标：方向准确率从当前60.5%提升至70%+

---

## 一、问题诊断（数据驱动）

### 1.1 核心数据

| 指标 | 值 | 评价 |
|------|-----|------|
| 总结算 | 177笔 | 样本充足 |
| **方向准确率** | **60.5% (109/177)** | ❌ 接近随机 |
| 区间命中率 | 62.1% | 一般 |
| MAE | 0.064% | ✅ 精度好 |
| 误差偏差 | +0.0025% | ✅ 无系统性偏 |
| 最长连错 | 4笔 | 可接受 |

### 1.2 五大致命问题

**问题1：强信号反而更差（最致命）**
```
强信号(conf≥65): 50.8% 方向准确率 ← 比随机还差！
弱信号(conf<65): 67.2% 方向准确率 ← 反而更好
```
**根因**：线性打分系统在极端值时恰恰是行情末端。SKILL.md已记录"引擎越自信越错"但未修复。这是**过度自信反转效应**——当多个指标同向打分到极端时，市场大概率在末端，下一步是反转。

**问题2：bull预测明显弱于bear**
```
bull: 57.3% (51/89)
bear: 63.0% (51/81)
neutral: 100% (7/7)
```
**根因**：BTC在样本期内偏向震荡/下行，但引擎bull倾向过强（89次bull vs 81次bear）。引擎对EMA金叉的bullish解读过激进。

**问题3：放量时准确率暴跌**
```
缩量(<40):    66.1%
正常(40-80):  56.1%
放量(80-120): 50.0%
巨量(120+):   50.0%
```
**根因**：放量意味着大单进入/清算事件，此时传统技术指标失效。当前引擎只是把放量当成"确认方向"，但放量常常意味着**方向即将反转**（大量清算=方向极端）。

**问题4：近期表现下滑**
```
早期(127笔): 64.6% MAE=0.070%
近期(50笔):  54.0% MAE=0.048%
```
**根因**：近期市场regime变化（可能是震荡市），引擎的trend-following性质在震荡中失效。

**问题5：高confidence区间70-79最差(44.4%)**
```
conf 70-79: 16/36 = 44.4% ← 最差
conf 80-89: 5/7  = 71.4% ← 样本小
conf 40-59: 62/97 = 63.9% ← 基准
```
**根因**：conf 70-79是"score=30-39"区间，刚好是direction_rule中"score>30"进入bull/bear的阈值。这个阈值设计不合理，太多噪声信号被判定为"有方向"。

---

## 二、优化方案

### 优化1：反转过度自信信号（预计+5-8%准确率）

**原理**：当引擎score极端（|score|>60）时，反转信号或降级为neutral。

**实施**：
```python
# 修改 direction_rule() 函数
if abs(score) > 60:
    # 极端信号 → 反转概率高
    # 降级strength为weak，或反转方向
    strength = "reversal_alert"
    confidence = min(70, 40 + abs(score) // 2)  # 压低confidence
```

**验证**：回测177笔数据中score>60的样本，看反转后的准确率。

### 优化2：引入OFI微结构因子（预计+5-10%准确率）

**原理**：OFI(订单流不平衡)对5分钟价格变化R²~15-25%，是目前缺失的最强预测因子。

**数据源**：Binance WebSocket `btcusdt@depth20@100ms`
- 最优买/卖价及深度
- 计算实时OFI和microprice

**实施**：
```python
def compute_ofi(depth_snapshots):
    """订单流不平衡 — Cont, Kukanov & Stoikov (2014)"""
    ofi = 0
    for i in range(1, len(depth_snapshots)):
        prev, curr = depth_snapshots[i-1], depth_snapshots[i]
        # Bid side
        if curr['bid_price'] > prev['bid_price']:
            ofi += curr['bid_qty']
        elif curr['bid_price'] == prev['bid_price']:
            ofi += curr['bid_qty'] - prev['bid_qty']
        else:
            ofi -= prev['bid_qty']
        # Ask side (mirror)
        if curr['ask_price'] > prev['ask_price']:
            ofi -= prev['ask_qty']
        elif curr['ask_price'] == prev['ask_price']:
            ofi -= (curr['ask_qty'] - prev['ask_qty'])
        else:
            ofi += curr['ask_qty']
    return ofi

def compute_microprice(bid_price, bid_qty, ask_price, ask_qty):
    """Stoikov (2018) microprice"""
    spread = ask_price - bid_price
    return bid_price + spread * bid_qty / (bid_qty + ask_qty)
```

**权重**：OFI作为独立信号，权重40%，与现有指标组合。

### 优化3：Regime-aware方向判定（预计+3-5%准确率）

**原理**：不同市场regime下，技术指标的有效性不同。
- 趋势市：EMA/MACD有效
- 震荡市：RSI/BB反转有效
- 高波动市：所有指标失效，应降权

**实施**：用波动率和趋势强度判断regime
```python
def detect_regime(candles, atr_val, closes):
    """简单的3-regime分类"""
    # 波动率
    vol = atr_val / closes[-1] * 100
    
    # 趋势强度 (EMA9 vs EMA21 角度)
    ema9_slope = (ema(closes[-10:], 9) - ema(closes[-20:-10], 9))
    
    if vol > 0.25:  # 高波动
        return "HIGH_VOL"
    elif abs(ema9_slope) > atr_val * 0.3:  # 有趋势
        return "TREND"
    else:
        return "RANGE"

# 然后根据regime调整权重
def adjusted_direction(regime, base_score):
    if regime == "HIGH_VOL":
        return "neutral", "weak", 40  # 高波动不判方向
    elif regime == "RANGE":
        # 震荡市反转策略
        if base_score > 20: return "bear", "weak", 45
        elif base_score < -20: return "bull", "weak", 45
        else: return "neutral", "weak", 40
    else:
        return None  # 使用原始逻辑
```

### 优化4：修正bull偏向（预计+2-3%准确率）

**原理**：当前score>0就判bull，score>-30也判bull(weak)。阈值不对称。

**实施**：
```python
# 修改阈值
if score > 25:      # 原来30，提高bull门槛
    bias = "bull"
elif score > 5:     # 原来0，小幅bullish不判方向
    bias = "neutral"  # 改为中性
    strength = "slight_bull"
elif score > -5:    # 新增中性区间
    bias = "neutral"
elif score > -25:   # 原来-30
    bias = "neutral"
    strength = "slight_bear"
else:
    bias = "bear"
```

**扩大neutral区间**：score在[-5, +5]范围判定neutral，避免对微弱信号下方向判断。

### 优化5：放量反转因子（预计+2-4%准确率）

**原理**：放量不是确认方向，而是**反转预警**。

**实施**：
```python
# 修改volume权重逻辑
if vol_pct > 120:
    # 巨量 → 反转信号
    score -= 15 * (1 if score > 0 else -1)  # 反转当前方向
elif vol_pct > 80:
    # 放量 → 减弱方向
    score *= 0.7
elif vol_pct < 40:
    # 缩量 → 维持当前判断（缩量时准确率最高66%）
    pass
```

### 优化6：连续K线疲劳因子（预计+1-2%准确率）

**原理**：连续3+根同方向K线后，下一根反转概率显著升高。

**实施**：
```python
# 增强 consecutive candle 逻辑
if consecutive_bull >= 3:
    score -= 15  # 原来只有-10，加强反转力度
    if consecutive_bull >= 5:
        score -= 25  # 5根以上强烈反转
elif consecutive_bear >= 3:
    score += 15
    if consecutive_bear >= 5:
        score += 25
```

---

## 三、实施优先级与验证方法

### Phase 1: 立即修复（今天）

| # | 优化 | 预期提升 | 复杂度 |
|---|------|---------|--------|
| 1 | 反转过度自信信号 | +5-8% | 低（改5行代码） |
| 4 | 修正bull偏向+扩大neutral | +2-3% | 低（改阈值） |
| 5 | 放量反转因子 | +2-4% | 低（改volume逻辑） |
| 6 | 连续K线疲劳 | +1-2% | 低（改权重） |

**合计预期**: +10-17% → 方向准确率 70-77%

### Phase 2: 一周内

| # | 优化 | 预期提升 | 复杂度 |
|---|------|---------|--------|
| 2 | OFI微结构因子 | +5-10% | 中（需WebSocket） |
| 3 | Regime-aware判定 | +3-5% | 中（需regime分类） |

### 验证方法

1. **历史回测**：用177笔已有数据的指标值（不含OFI），模拟Phase 1修改后的判定结果
2. **Walk-forward**：Phase 1修改后，运行7天实盘纸盘，跟踪准确率
3. **A/B对比**：保留旧引擎逻辑，新旧引擎并行运行，对比准确率差异

---

## 四、与蒸馏知识的对齐

| 优化方案 | 蒸馏来源 | 核心理论 |
|---------|---------|---------|
| OFI因子 | R09微结构 | Cont, Kukanov & Stoikov (2014) |
| Microprice | R09微结构 | Stoikov (2018) |
| Regime检测 | R10风险管理 | HMM/波动率regime |
| 反转信号 | R01因子理论 | 动量因子的IC衰减与反转 |
| 信号组合 | R11机构方法论 | Simons: 每个信号独立验证IC |
| Neutral区间 | R02策略理论 | OU过程的均值回归区域 |
| 放量反转 | R09微结构 | Kyle Lambda: 大单=信息交易 |

---

## 五、长期目标（v5.0架构）

```
当前v4.0:  线性打分(EMA+RSI+MACD+Vol) → LLM覆盖
          方向准确率: 60.5%

Phase 1:   反转+修正+扩大neutral
          目标: 70-77%

Phase 2:   +OFI+Regime
          目标: 75-85%

v5.0:      多模型集成(LightGBM+TFT+贝叶斯)
          +OFI+Microprice+Regime+IV
          目标: 80%+
```

> Simons哲学: "不要相信单一信号。每个信号独立验证，只组合IC>0.05的因子。"
> 优先级: 夏普>回撤>年化 → 方向准确率是夏普的基础
