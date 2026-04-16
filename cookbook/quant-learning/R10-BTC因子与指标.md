# R10: BTC因子与指标

> 学习日期: 2026-04-03 | 难度: ⭐⭐⭐ 进阶

---

## 一、BTC因子分类

BTC量化交易的因子体系与传统金融有显著不同，最大的区别在于**链上数据**维度。

```
BTC因子体系:

├── 技术因子 (Technical)
│   ├── 价格动量
│   ├── 成交量
│   ├── 波动率
│   └── 技术形态
│
├── 链上因子 (On-Chain)
│   ├── 活跃地址数
│   ├── 交易所净流入
│   ├── 矿工行为
│   ├── HODL指标
│   └── 大额交易
│
├── 情绪因子 (Sentiment)
│   ├── 恐惧贪婪指数
│   ├── 社交媒体情绪
│   ├── 搜索热度
│   └── 资金费率
│
└── 宏观因子 (Macro)
    ├── 美元指数
    ├── 美债收益率
    ├── 股市相关性
    └── 流动性指标
```

---

## 二、技术指标

### 2.1 价格动量因子

```python
import pandas as pd
import numpy as np

def calc_momentum_factors(df):
    """
    计算BTC动量因子
    df: DataFrame with 'close', 'volume', 'high', 'low'
    """
    # === 收益率动量 ===
    for n in [4, 12, 24, 72, 168]:  # 4h, 12h, 1d, 3d, 7d (小时线)
        df[f'ret_{n}h'] = df['close'].pct_change(n)

    # === EMA偏离度 ===
    for n in [12, 26, 50, 200]:
        df[f'ema{n}'] = df['close'].ewm(span=n).mean()
        df[f'ema{n}_bias'] = df['close'] / df[f'ema{n}'] - 1

    # === RSI ===
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['RSI_14'] = 100 - (100 / (1 + rs))

    # === MACD ===
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']

    return df
```

### 2.2 成交量因子

```python
def calc_volume_factors(df):
    """成交量因子"""
    # === OBV (On-Balance Volume) ===
    direction = np.sign(df['close'].diff())
    df['OBV'] = (direction * df['volume']).cumsum()
    df['OBV_MA'] = df['OBV'].rolling(24).mean()

    # === VWAP ===
    df['VWAP'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()

    # === 成交量比率 ===
    df['vol_ratio'] = df['volume'] / df['volume'].rolling(24).mean()

    # === 量价背离 ===
    price_trend = df['close'].pct_change(24)
    vol_trend = df['volume'].pct_change(24)
    df['price_vol_diverge'] = price_trend - vol_trend.rank(pct=True)

    return df
```

### 2.3 波动率因子

```python
def calc_volatility_factors(df):
    """波动率因子"""
    # === 历史波动率 ===
    df['realized_vol_1d'] = df['close'].pct_change().rolling(24).std() * np.sqrt(24*365)
    df['realized_vol_7d'] = df['close'].pct_change().rolling(168).std() * np.sqrt(24*365)

    # === ATR (Average True Range) ===
    tr = pd.DataFrame({
        'hl': df['high'] - df['low'],
        'hc': (df['high'] - df['close'].shift(1)).abs(),
        'lc': (df['low'] - df['close'].shift(1)).abs()
    }).max(axis=1)
    df['ATR_14'] = tr.rolling(14).mean()
    df['ATR_ratio'] = df['ATR_14'] / df['close']  # ATR占比

    # === 波动率偏度 ===
    ret = df['close'].pct_change()
    df['vol_skew'] = ret.rolling(168).skew()

    # === Parkinson波动率 ===
    df['parkinson_vol'] = (
        np.sqrt(
            (1 / (4 * 24 * np.log(2))) *
            (np.log(df['high'] / df['low'])**2).rolling(24).sum()
        ) * np.sqrt(365 * 24)
    )

    return df
```

---

## 三、链上数据因子

### 3.1 核心链上指标

| 指标 | 说明 | 获取方式 | 预测能力 |
|------|------|----------|----------|
| **活跃地址数** | 每日活跃地址 | Glassnode/Blockchain.com | 网络使用度 |
| **交易所净流入** | 流入-流出交易所 | Glassnode | 卖压信号 |
| **矿工持仓** | 矿工地址余额变化 | Glassnode | 供给压力 |
| **NUPL** | 净未实现盈亏 | Glassnode | 市场情绪 |
| **SOPR** | 支出输出利润率 | Glassnode | 盈利/亏损 |
| **MVRV** | 市值/实现市值 | Glassnode | 高估/低估 |
| **HODL Waves** | 按持有时间分类 | Glassnode | 长期持有者行为 |

### 3.2 关键链上因子计算

```python
# 需要Glassnode API (https://glassnode.com)
# pip install glassnode

import requests
import pandas as pd

class GlassnodeAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = 'https://api.glassnode.com/v1/metrics'

    def get_metric(self, metric, asset='BTC', interval='24h'):
        """获取链上指标"""
        url = f"{self.base_url}/{metric}"
        params = {
            'a': asset,
            'i': interval,
            'api_key': self.api_key
        }
        response = requests.get(url, params=params)
        data = response.json()

        df = pd.DataFrame(data)
        df['t'] = pd.to_datetime(df['t'], unit='s')
        df.set_index('t', inplace=True)
        return df

    # 常用指标
    def active_addresses(self):
        return self.get_metric('addresses/active_count')

    def exchange_net_position(self):
        """交易所净持仓变化"""
        return self.get_metric('transactions/transfers/volume_sum')

    def nupl(self):
        """净未实现盈亏"""
        return self.get_metric('indicators/nupl')

    def sopr(self):
        """支出输出利润率"""
        return self.get_metric('indicators/sopr')

    def mvrv(self):
        """市值/实现市值"""
        return self.get_metric('market/mvrv')

    def hash_rate(self):
        """算力"""
        return self.get_metric('mining/hash_rate_mean')
```

### 3.3 链上因子信号

```python
def generate_onchain_signals(mvrv_df, nupl_df, sopr_df, exchange_flow_df):
    """
    综合链上信号
    返回: -1 到 1 的信号（负=看跌，正=看涨）
    """
    signals = {}

    # MVRV > 3.5 → 市场过热（看跌）
    # MVRV < 1 → 市场低估（看涨）
    latest_mvrv = mvrv_df['v'].iloc[-1]
    if latest_mvrv > 3.5:
        signals['mvrv'] = -1
    elif latest_mvrv < 1:
        signals['mvrv'] = 1
    else:
        signals['mvrv'] = 0

    # NUPL > 0.75 → 贪婪（看跌）
    # NUPL < 0 → 恐惧（看涨）
    latest_nupl = nupl_df['v'].iloc[-1]
    if latest_nupl > 0.75:
        signals['nupl'] = -1
    elif latest_nupl < 0:
        signals['nupl'] = 1
    else:
        signals['nupl'] = 0

    # SOPR > 1 → 持有者盈利（可能卖出）
    # SOPR < 1 → 持有者亏损（可能继续持有）
    latest_sopr = sopr_df['v'].iloc[-1]
    if latest_sopr > 1.1:
        signals['sopr'] = -0.5
    elif latest_sopr < 0.9:
        signals['sopr'] = 0.5
    else:
        signals['sopr'] = 0

    # 综合信号
    composite = np.mean(list(signals.values()))
    return composite, signals
```

---

## 四、情绪指标

### 4.1 恐惧贪婪指数

```python
def get_fear_greed_index():
    """获取恐惧贪婪指数"""
    url = 'https://api.alternative.me/fng/?limit=30'
    response = requests.get(url)
    data = response.json()

    df = pd.DataFrame(data['data'])
    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='s')
    df.set_index('timestamp', inplace=True)
    df['value'] = df['value'].astype(int)

    return df

# 使用：
# 0-25: 极度恐惧 → 买入信号
# 25-45: 恐惧
# 45-55: 中性
# 55-75: 贪婪
# 75-100: 极度贪婪 → 卖出信号
```

### 4.2 资金费率

```python
import ccxt

def get_funding_rate(symbol='BTC/USDT:USDT'):
    """获取永续合约资金费率"""
    exchange = ccxt.binance({'enableRateLimit': True})
    funding = exchange.fetch_funding_rate_history(symbol, limit=100)

    df = pd.DataFrame(funding)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)

    return df

# 资金费率解读：
# 正费率 → 多头付费 → 多头过热 → 可能回调
# 负费率 → 空头付费 → 空头过热 → 可能反弹
# 极端正/负费率 → 反向信号
```

### 4.3 持仓分布 (Open Interest)

```python
def get_open_interest(symbol='BTC/USDT:USDT'):
    """获取持仓量数据"""
    exchange = ccxt.binance({'enableRateLimit': True})

    # 总持仓量
    oi = exchange.fetch_open_interest_history('BTC/USDT:USDT', timeframe='1h', limit=168)

    df = pd.DataFrame(oi)
    return df

# OI + 价格 组合信号：
# 价格↑ + OI↑ → 趋势加强
# 价格↑ + OI↓ → 空头平仓，趋势可能结束
# 价格↓ + OI↑ → 新空头入场，趋势可能持续
# 价格↓ + OI↓ → 多头平仓，底部可能到来
```

---

## 五、综合因子模型

```python
class BTCFactorModel:
    """BTC综合因子模型"""

    def __init__(self):
        self.factors = {}

    def calculate_all_factors(self, price_df, onchain_data=None):
        """计算所有因子"""
        # 技术因子
        price_df = calc_momentum_factors(price_df)
        price_df = calc_volume_factors(price_df)
        price_df = calc_volatility_factors(price_df)

        # 综合得分
        # 动量得分
        mom_score = (
            price_df['ret_24h'].rank(pct=True) * 0.3 +
            price_df['RSI_14'].rank(pct=True) * 0.2 +
            (price_df['MACD_hist'] > 0).astype(float) * 0.2 +
            price_df['vol_ratio'].rank(pct=True) * 0.15 +
            (1 - price_df['ATR_ratio'].rank(pct=True)) * 0.15
        )

        return mom_score
```

---

## 六、信息源

| 来源 | 链接 | 数据类型 |
|------|------|----------|
| Glassnode | https://glassnode.com | 链上数据 |
| CryptoQuant | https://cryptoquant.com | 链上/交易所数据 |
| CoinGecko | https://www.coingecko.com | 市场数据 |
| Fear & Greed | https://alternative.me/crypto/fear-and-greed-index/ | 情绪指数 |
| Santiment | https://santiment.net | 社交+链上 |
| IntoTheBlock | https://intothetheblock.com | 链上分析 |

---

*下一报告: R11-BTC回测框架.md → Freqtrade/Jesse/CCXT*
