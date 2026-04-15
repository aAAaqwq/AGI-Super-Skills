# 5分钟BTC盘参数配置 v2.0

**最后更新**: 2026-03-12
**基于**: 5min-research R1-R8综合研究

---

## 1. 信号参数

### 1.1 技术指标

| 参数 | 值 | 说明 |
|------|-----|------|
| EMA_SHORT | 9 | 短期EMA周期 |
| EMA_LONG | 21 | 长期EMA周期 |
| RSI_PERIOD | 14 | RSI周期 |
| RSI_OVERSOLD | 30 | RSI超卖阈值 |
| RSI_OVERBOUGHT | 70 | RSI超买阈值 |

### 1.2 动量策略参数 (亚盘)

| 参数 | 值 | 说明 |
|------|-----|------|
| MOMENTUM_CONSECUTIVE | 2 | 连续同向周期数 |
| MOMENTUM_MIN_RANGE | 50 | 最小波幅($), 过滤噪音 |
| MOMENTUM_LOOKBACK | 5 | 回看周期数 |

### 1.3 均值回归参数 (美盘)

| 参数 | 值 | 说明 |
|------|-----|------|
| REVERSION_THRESHOLD | 200 | 极端波动触发($) |
| REVERSION_RSI_EXTREME | 75/25 | RSI极值阈值(强化) |

### 1.4 信号组合

| 参数 | 值 | 说明 |
|------|-----|------|
| MIN_SIGNALS | 2 | 最少信号数才入场 |
| SIGNAL_STRENGTH_1 | 0.50 | 1信号仓位($) |
| SIGNAL_STRENGTH_2 | 1.00 | 2信号仓位($) |
| SIGNAL_STRENGTH_3 | 2.00 | 3信号仓位($) |

---

## 2. 时段参数

### 2.1 时段定义 (UTC)

| 时段 | 开始 | 结束 | 策略 |
|------|------|------|------|
| ASIAN_MOMENTUM | 03:00 | 07:00 | 动量延续 |
| EUROPEAN_TRANSITION | 08:00 | 14:00 | 观望/轻仓 |
| US_REVERSION | 15:00 | 18:00 | 均值回归 |
| DANGER_ZONE | 13:00 | 14:00 | 禁止交易 |
| LATE_NIGHT | 21:00 | 03:00 | 观望 |

### 2.2 时段仓位系数

| 时段 | 系数 | 说明 |
|------|------|------|
| 亚盘动量 | 1.2x | 波动低，可放大 |
| 欧盘过渡 | 0.5x | 不确定高 |
| 美盘回归 | 0.6x | 波动高，需缩小 |
| 危险时段 | 0x | 禁止交易 |
| 深夜 | 0.3x | 流动性低 |

### 2.3 时段止损设置

| 时段 | 止损($) | 基于波幅 |
|------|---------|----------|
| 亚盘 | 60 | 0.5×$108 |
| 欧盘 | 100 | 0.6×$170 |
| 美盘 | 120 | 0.5×$246 |

---

## 3. Kelly仓位参数

### 3.1 Kelly公式

```
f* = (b*p - q) / b

其中:
- b = 赔率 = (1-买入价)/买入价
- p = 胜率
- q = 1-p
```

### 3.2 Kelly系数

| 参数 | 值 | 说明 |
|------|-----|------|
| KELLY_FRACTION | 0.5 | 使用半Kelly |
| KELLY_MAX | 0.20 | Kelly上限20% |
| DEFAULT_WIN_RATE | 0.55 | 默认胜率估计 |

### 3.3 仓位硬上限

| 参数 | 值 | 说明 |
|------|-----|------|
| MAX_POSITION_PCT | 0.05 | 单笔最大5%资金 |
| MAX_POSITION_USD | 5 | 单笔最大$5 |
| MIN_POSITION_USD | 1 | 单笔最小$1 |

---

## 4. 风控参数

### 4.1 连亏保护

| 参数 | 值 | 动作 |
|------|-----|------|
| LOSS_STREAK_HALF | 3 | 仓位减半 |
| LOSS_STREAK_PAUSE | 5 | 暂停30分钟 |
| PAUSE_DURATION_MIN | 30 | 暂停时长(分钟) |

### 4.2 日亏损上限

| 参数 | 值 | 动作 |
|------|-----|------|
| DAILY_LOSS_LIMIT | -0.10 | 当日停止交易 |

### 4.3 连胜加码

| 参数 | 值 | 动作 |
|------|-----|------|
| WIN_STREAK_BOOST1 | 3 | 仓位×1.5 |
| WIN_STREAK_BOOST2 | 5 | 仓位×2.0 |
| WIN_STREAK_MAX | 2.0 | 最大加码倍数 |

---

## 5. 数据源参数

### 5.1 Binance API

| 参数 | 值 |
|------|-----|
| SYMBOL | BTCUSDT |
| INTERVAL | 1m |
| LOOKBACK | 30 |
| TIMEOUT_SEC | 10 |

### 5.2 Polymarket API

| 参数 | 值 |
|------|-----|
| SERIES_SLUG | btc-up-or-down-5m |
| MIN_LIQUIDITY | 5000 |

---

## 6. 修改历史

| 日期 | 版本 | 变更 | 原因 |
|------|------|------|------|
| 2026-03-11 | v1.0 | 初始参数 | 基线设定 |
| 2026-03-12 | v2.0 | 时段自适应+Kelly风控 | R1-R8研究综合 |

---

## 7. 参数速查表

```
# 快速参考 - 用于脚本

# 技术指标
EMA_SHORT=9
EMA_LONG=21
RSI_PERIOD=14
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70

# 信号阈值
MOMENTUM_CONSECUTIVE=2
MOMENTUM_MIN_RANGE=50
REVERSION_THRESHOLD=200
MIN_SIGNALS=2

# Kelly
KELLY_FRACTION=0.5
KELLY_MAX=0.20
DEFAULT_WIN_RATE=0.55

# 仓位
MAX_POSITION_USD=5
MIN_POSITION_USD=1

# 风控
LOSS_STREAK_HALF=3
LOSS_STREAK_PAUSE=5
DAILY_LOSS_LIMIT=-0.10
WIN_STREAK_BOOST1=3
WIN_STREAK_BOOST2=5

# 时段 (UTC小时)
ASIAN_START=3
ASIAN_END=7
US_START=15
US_END=18
DANGER_START=13
DANGER_END=14
```
