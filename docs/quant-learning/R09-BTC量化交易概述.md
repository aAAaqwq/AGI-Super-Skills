# R09: BTC量化交易概述

> 学习日期: 2026-04-03 | 难度: ⭐⭐ 基础

---

## 一、加密市场结构

### 1.1 与传统市场的核心差异

| 维度 | A股 | BTC |
|------|-----|-----|
| **交易时间** | 9:30-15:00 (工作日) | **7×24×365** |
| **涨跌幅** | ±10%/±20% | **无限制** |
| **T+N** | T+1 | **T+0** |
| **做空** | 融券（受限） | **自由做空（合约）** |
| **杠杆** | 融资融券1:1 | **最高125x** |
| **交易对** | CNY | USDT/BUSD/USD |
| **结算** | 人民币 | 稳定币/法币 |
| **监管** | 证监会 | 各国不同（宽松→收紧） |
| **入金门槛** | 无限制 | 因交易所而异 |
| **手续费** | ~万3 + 千1印花税 | Maker: 0.02%, Taker: 0.05% |

### 1.2 市场参与者

```
BTC市场参与者图谱:

┌─────────────────────────────────────────┐
│              交易所 (Exchange)            │
│   Binance / OKX / Bybit / Coinbase      │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┼──────────────┐
    ▼          ▼              ▼
┌────────┐ ┌──────────┐ ┌──────────┐
│ 散户    │ │ 量化基金  │ │ 做市商    │
│ (多数)  │ │ (算法交易)│ │ (流动性)  │
└────────┘ └──────────┘ └──────────┘
               │
    ┌──────────┼──────────────┐
    ▼          ▼              ▼
┌────────┐ ┌──────────┐ ┌──────────┐
│ 矿工    │ │ 套利者    │ │ DeFi协议  │
│ (抛压)  │ │ (搬砖)   │ │ (AMM)    │
└────────┘ └──────────┘ └──────────┘
```

### 1.3 市场数据特征

| 特征 | 数据 | 说明 |
|------|------|------|
| **日均波动率** | 3-5% | A股日均波动率约1-2% |
| **年化波动率** | 60-80% | 极高波动 |
| **与美股相关性** | 0.3-0.5 | 近年增强 |
| **周末效应** | 显著 | 周末流动性更低、波动更大 |
| **减半周期** | ~4年一次 | 影响供给量 |
| **链上透明** | 全部公开 | 独特的链上数据维度 |

---

## 二、交易所生态

### 2.1 主要交易所

| 交易所 | 日均交易量 | 特点 | API质量 |
|--------|-----------|------|---------|
| **Binance** | $20-50B | 最大、最全 | ⭐⭐⭐⭐⭐ |
| **OKX** | $10-20B | 中国用户友好 | ⭐⭐⭐⭐⭐ |
| **Bybit** | $5-15B | 合约为核心 | ⭐⭐⭐⭐ |
| **Coinbase** | $2-5B | 美国合规 | ⭐⭐⭐⭐ |
| **Bitget** | $5-10B | 跟单交易 | ⭐⭐⭐ |

### 2.2 交易产品类型

| 产品 | 说明 | 杠杆 | 风险 |
|------|------|------|------|
| **现货** | 直接买卖BTC | 1x | 低 |
| **U本位合约** | 以USDT结算 | 1-125x | 高 |
| **币本位合约** | 以BTC结算 | 1-100x | 高 |
| **期权** | 买权/卖权 | 非线性 | 极高 |
| **杠杆代币** | 自动调杠杆 | 1-3x | 中高 |

---

## 三、BTC量化优势与挑战

### 3.1 优势

| 优势 | 说明 |
|------|------|
| **T+0** | 可以日内无限次交易 |
| **7×24** | 不受交易时间限制 |
| **API友好** | 交易所API设计完善 |
| **无涨跌停** | 信号可以完全执行 |
| **做空自由** | 合约做空无门槛 |
| **链上数据** | 额外的数据维度 |
| **低门槛** | 几十美元即可开始 |

### 3.2 挑战

| 挑战 | 说明 |
|------|------|
| **高波动** | 止损容易被滑 |
| **黑天鹅多** | 插针、交易所宕机 |
| **监管不确定** | 各国政策变化 |
| **交易所风险** | 跑路、被盗 (FTX案例) |
| **流动性分化** | BTC流动性好，山寨币差 |
| **资金安全** | 需要安全的存储方案 |

---

## 四、BTC量化入门架构

### 4.1 系统架构

```
┌──────────────────────────────────────┐
│            数据层 (Data Layer)         │
│  行情API / 链上数据 / 社交媒体情绪     │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│          策略层 (Strategy Layer)       │
│  信号生成 / 因子计算 / ML模型          │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│          执行层 (Execution Layer)      │
│  订单管理 / 仓位管理 / 风控             │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│          基础设施 (Infrastructure)     │
│  VPS / API密钥 / 数据库 / 监控告警     │
└──────────────────────────────────────┘
```

### 4.2 快速开始代码

```python
# pip install ccxt pandas numpy

import ccxt
import pandas as pd
import numpy as np
import time

# 连接Binance
exchange = ccxt.binance({
    'apiKey': 'your_api_key',
    'secret': 'your_secret',
    'enableRateLimit': True,
})

# 获取BTC行情
def get_btc_klines(symbol='BTC/USDT', timeframe='1h', limit=500):
    """获取K线数据"""
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

# 简单的动量策略
def momentum_strategy(df, lookback=24, holding=4):
    """
    动量策略
    lookback: 回看期（小时数）
    holding: 持有期（小时数）
    """
    df['return'] = df['close'].pct_change(lookback)
    df['signal'] = 0

    # 正收益做多，负收益做空
    df.loc[df['return'] > 0, 'signal'] = 1
    df.loc[df['return'] < 0, 'signal'] = -1

    # 计算策略收益
    df['strategy_return'] = df['signal'].shift(1) * df['close'].pct_change()

    # 统计
    total = (1 + df['strategy_return']).prod() - 1
    sharpe = df['strategy_return'].mean() / df['strategy_return'].std() * np.sqrt(365*24)

    print(f"总收益: {total:.2%}")
    print(f"夏普比率: {sharpe:.2f}")
    print(f"最大回撤: {((1+df['strategy_return']).cumprod().cummax() / (1+df['strategy_return']).cumprod() - 1).max():.2%}")

    return df

# 运行
df = get_btc_klines()
result = momentum_strategy(df)
```

---

## 五、资金管理

### 5.1 安全方案

| 方案 | 安全性 | 便利性 | 适合 |
|------|--------|--------|------|
| **交易所内** | ⭐⭐ | ⭐⭐⭐⭐⭐ | 交易资金 |
| **热钱包** | ⭐⭐⭐ | ⭐⭐⭐⭐ | 中等金额 |
| **冷钱包** | ⭐⭐⭐⭐⭐ | ⭐⭐ | 长期存储 |
| **硬件钱包** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 大额存储 |

### 5.2 API密钥安全

```python
# 使用环境变量存储密钥
import os

API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')

# 或使用 pass (Linux)
# import subprocess
# API_KEY = subprocess.run(['pass', 'show', 'api/binance'], capture_output=True, text=True).stdout.strip()

# API权限设置建议：
# - 只开启"交易"权限
# - 不开启"提现"权限
# - 绑定IP白名单
```

---

## 六、信息源

| 来源 | 链接 | 说明 |
|------|------|------|
| Binance API文档 | https://binance-docs.github.io/apidocs | 最全的交易API |
| OKX API文档 | https://www.okx.com/docs-v5 | OKX V5 API |
| CCXT文档 | https://docs.ccxt.com | 统一交易接口 |
| CoinGecko | https://www.coingecko.com | 免费市场数据 |
| Glassnode | https://glassnode.com | 链上数据 |
| TradingView | https://www.tradingview.com | 技术分析 |

---

## 七、实战建议

### 入门路径
1. **第1周**：注册Binance/OKX，熟悉界面，小额充值
2. **第2周**：用CCXT获取数据，分析BTC价格特征
3. **第3-4周**：用Freqtrade回测简单策略
4. **第5-8周**：模拟盘交易（Binance Testnet）
5. **第9-12周**：小资金实盘（$100-500）

### 避坑指南
- ❌ **不要高杠杆**：新手用1-3x足够，5x以上是赌博
- ❌ **不要把全部资金放交易所**：只放交易所需的
- ❌ **不要忽视资金费率**：合约持仓有资金费率成本
- ✅ **先用Testnet**：Binance/OKX都有测试网
- ✅ **做好风控**：止损是生命线

---

*下一报告: R10-BTC因子与指标.md → 链上数据/技术指标/情绪指标*
