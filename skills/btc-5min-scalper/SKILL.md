---
name: btc-5min-scalper
description: "BTC 5-minute Up/Down paper trading on Polymarket. Scans Binance 1m candles for momentum/mean-reversion/volume signals, makes virtual trades on Polymarket 5-min markets, tracks P&L. Use when: (1) scanning BTC 5-min trading signals, (2) running paper trade simulations, (3) reviewing 5-min strategy performance, (4) iterating scalping strategy parameters. Trigger: 'btc 5min', '5分钟', 'scalper', 'paper trade', '纸盘', '模拟盘'."
---

# BTC 5-Min Scalper — Paper Trading System

Polymarket的"Bitcoin Up or Down - 5 Minutes"市场模拟交易系统。

## 市场结构

- **玩法**: 5分钟窗口内BTC涨(Up)还是跌(Down)
- **赔率**: ~50/50 (Up 49-52¢ / Down 48-51¢)
- **结算**: Chainlink BTC/USD，窗口结束价 vs 开始价
- **频率**: 每5分钟一场，连续24/7
- **URL模式**: `polymarket.com/event/btc-updown-5m-{unix_timestamp}`

## 信号系统 (6层)

运行信号扫描: `bash scripts/scan_signals.sh`

| ID | 策略 | 触发条件 | 方向 | 置信度 |
|----|------|----------|------|--------|
| S1 | 动量跟随 | 最近3根1m K线同向 | 跟随 | 中 |
| S2 | 均值回归 | 5min累计波动 > ±$150 | 反向 | 中高 |
| S3 | 放量突破 | 最新vol > 2x近25根均值 | 跟随放量方向 | 高 |
| S4 | RSI极值 | 1m RSI <25或>75 | 反向 | 中 |
| S5 | 赔率偏差 | Polymarket Up/Down偏离>55/45 | 逆向 | 低 |
| **S6** | **支撑/阻力位** | **价格接近24h高低点或整数关口** | **反弹/突破** | **中高** |

### S6 支撑/阻力位策略 (3/12新增)

**核心思想**: 价格不是随机游走，关键价位有"记忆"。

**识别方法**:
```bash
# 获取支撑/阻力位
curl -s 'https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT' | jq '{high:.highPrice,low:.lowPrice}'
curl -s 'https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=24' | python3 -c "
import json,sys
candles=json.load(sys.stdin)
lows=[float(k[3]) for k in candles]
highs=[float(k[2]) for k in candles]
price=float(candles[-1][4])
support=min(lows)
resistance=max(highs)
print(f'现价: ${price:,.0f}')
print(f'24h支撑: ${support:,.0f} (距{(price-support)/price*100:.1f}%)')
print(f'24h阻力: ${resistance:,.0f} (距{(resistance-price)/price*100:.1f}%)')
# 整数关口
for level in range(int(price//1000)*1000, int(price//1000+2)*1000, 1000):
    dist=(level-price)/price*100
    if abs(dist)<2:
        print(f'整数关口: ${level:,} (距{dist:+.1f}%)')
"
```

**信号规则**:
- 价格距支撑位<0.3% + 前一根K线下影线长 → **UP信号** (支撑反弹)
- 价格距阻力位<0.3% + 前一根K线上影线长 → **DOWN信号** (阻力压制)
- 价格突破阻力位(收盘>阻力) + 放量 → **UP信号** (突破跟随)
- 价格跌破支撑位(收盘<支撑) + 放量 → **DOWN信号** (破位跟随)

**与其他策略协同**:
- S6支撑反弹 + S2均值回归 → 高置信度组合
- S6突破 + S3放量 → 高置信度组合
- S6阻力压制 + S1下跌动量 → 做空信号增强

### 入场规则
- **≥2个策略同向** → 入场，虚拟$2
- **1个信号** → SKIP，记录倾向
- **0个信号** → SKIP

### 出场规则
- 持有到5min窗口结算，不中途退出
- 每笔固定$2（虚拟），不加仓

## 工作流

### 1. 扫描信号
```bash
bash scripts/scan_signals.sh
```
输出各策略信号状态和综合建议。

### 2. 记录交易
将结果追加到 `data/paper-trading/YYYY-MM-DD.md`:
- 窗口时间、BTC价格、触发的信号
- 决策(ENTER/SKIP)、方向(UP/DOWN)、入场赔率
- 结果(WIN/LOSS)、P&L

### 3. 更新统计
更新 `data/paper-trading/strategy-stats.json`:
- 各策略独立胜率
- 组合信号胜率
- 累计虚拟P&L

### 4. 迭代优化
每积累20笔交易后，分析:
- 哪个策略胜率最高？
- 哪些组合最赚钱？
- 阈值是否需要调整？
将发现记录到 `references/iteration-log.md`

## 阈值参数 (可调)

见 `references/parameters.md` — 所有可调参数集中管理。

## 关键约束
- ⚠️ **绝不真实下单** — 纯模拟！
- 虚拟本金: $100
- 单笔: $2 (2%)
- 数据源: Binance API (`api.binance.com/api/v3/klines`)
- 赔率: 赢返$2/赔率 (如50¢买入，赢返$4，净赚$2)
- 亏损: 失去$2
