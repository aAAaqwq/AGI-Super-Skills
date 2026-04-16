# R11: BTC回测框架

> 学习日期: 2026-04-03 | 难度: ⭐⭐⭐ 进阶

---

## 一、框架对比

| 维度 | Freqtrade | Jesse | Backtrader+CCXT | 自研 |
|------|-----------|-------|-----------------|------|
| **语言** | Python | Python | Python | 任意 |
| **专注** | 加密货币 | 加密货币 | 通用 | 自定义 |
| **易用性** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **灵活性** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **实盘支持** | ✅ | ✅ | 需自研 | 需自研 |
| **社区** | 活跃 | 中等 | 活跃 | - |
| **文档** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | - |
| **机器学习** | ✅ FreqAI | ❌ | 需自研 | 需自研 |
| **费用** | 免费 | 免费 | 免费 | - |
| **推荐** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 二、Freqtrade（推荐）

### 2.1 安装与配置

```bash
# 安装
pip install freqtrade

# 或使用Docker（推荐）
docker pull freqtradeorg/freqtrade:stable

# 初始化
freqtrade create-userdir --userdir user_data
freqtrade new-config --config config.json
```

### 2.2 策略编写

```python
# user_data/strategies/my_strategy.py

from freqtrade.strategy import IStrategy, informative
from pandas import DataFrame
import talib.abstract as ta

class MyBTCStrategy(IStrategy):
    """
    BTC/USDT 简单策略
    - EMA交叉入场
    - RSI过滤
    - 追踪止损
    """

    # 基本参数
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = True  # 允许做空

    # 风控参数
    minimal_roi = {
        "0": 0.10,    # 10%止盈
        "60": 0.05,   # 1小时后5%止盈
        "120": 0.02,  # 2小时后2%止盈
    }
    stoploss = -0.05   # 5%止损
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # 启动资金
    startup_candle_count = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """计算指标"""

        # EMA
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=26)

        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macd_signal'] = macd['macdsignal']
        dataframe['macd_hist'] = macd['macdhist']

        # BB
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2, nbdevdn=2)
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_lower'] = bollinger['lowerband']

        # 成交量MA
        dataframe['volume_ma'] = dataframe['volume'].rolling(20).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """入场条件"""
        # 做多条件
        dataframe.loc[
            (
                (dataframe['ema_fast'] > dataframe['ema_slow']) &  # EMA金叉
                (dataframe['rsi'] < 70) &                          # RSI不过热
                (dataframe['volume'] > dataframe['volume_ma'])     # 放量
            ),
            'enter_long'] = 1

        # 做空条件
        dataframe.loc[
            (
                (dataframe['ema_fast'] < dataframe['ema_slow']) &  # EMA死叉
                (dataframe['rsi'] > 30) &                          # RSI不过冷
                (dataframe['volume'] > dataframe['volume_ma'])     # 放量
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """出场条件"""
        # 多头出场
        dataframe.loc[
            (
                (dataframe['ema_fast'] < dataframe['ema_slow']) |  # EMA死叉
                (dataframe['rsi'] > 80)                             # RSI超买
            ),
            'exit_long'] = 1

        # 空头出场
        dataframe.loc[
            (
                (dataframe['ema_fast'] > dataframe['ema_slow']) |  # EMA金叉
                (dataframe['rsi'] < 20)                             # RSI超卖
            ),
            'exit_short'] = 1

        return dataframe
```

### 2.3 回测运行

```bash
# 下载数据
freqtrade download-data \
    --exchange binance \
    --pairs BTC/USDT \
    --timeframes 1h \
    --timerange 20230101-20241231

# 回测
freqtrade backtesting \
    --strategy MyBTCStrategy \
    --timeframe 1h \
    --timerange 20230101-20241231 \
    --config config.json

# 参数优化
freqtrade hyperopt \
    --strategy MyBTCStrategy \
    --hyperopt-loss SharpeHyperOptLossDaily \
    --epochs 500 \
    --spaces buy sell roi stoploss
```

### 2.4 FreqAI（机器学习集成）

```python
# 使用FreqAI的ML策略
from freqtrade.strategy import IStrategy
from freqtrade.freqai.prediction_models import XGBoostRegressor

class FreqAIStrategy(IStrategy):
    """
    FreqAI + XGBoost 策略
    """
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = True

    # FreqAI配置
    freqai = {
        "enabled": True,
        "purge_old_models": 5,
        "train_period_days": 180,
        "backtest_period_days": 30,
        "identifier": "btc_xgboost",
        "feature_parameters": {
            "include_timeframes": ["1h", "4h"],
            "include_corr_pairlist": ["ETH/USDT"],
            "indicator_periods_candles": [10, 20, 50],
            "noise_standard_deviation": 0.02,
        },
        "model_training_parameters": {
            "n_estimators": 200,
            "max_depth": 6,
        },
        "data_split_parameters": {
            "test_size": 0.2,
            "random_state": 42,
        },
    }

    def feature_engineering_expand_all(self, dataframe, period, **kwargs):
        dataframe['%-rsi'] = ta.RSI(dataframe, timeperiod=period)
        dataframe['%-ema'] = ta.EMA(dataframe, timeperiod=period)
        dataframe['%-bb_width'] = (
            ta.BBANDS(dataframe, timeperiod=period)['upperband'] -
            ta.BBANDS(dataframe, timeperiod=period)['lowerband']
        ) / ta.BBANDS(dataframe, timeperiod=period)['middleband']
        return dataframe

    def feature_engineering_expand_basic(self, dataframe, **kwargs):
        dataframe['%-pct_change'] = dataframe['close'].pct_change()
        dataframe['%-raw_volume'] = dataframe['volume']
        return dataframe

    def set_freqai_targets(self, dataframe, **kwargs):
        dataframe['&-s-close'] = (
            dataframe['close'].shift(-self.freqai_info["backtest_period_days"])
        )
        return dataframe
```

---

## 三、Jesse

### 3.1 安装

```bash
pip install jesse
jesse init my-bot
cd my-bot
```

### 3.2 策略示例

```python
# strategies/BTCMomentum.py

import jesse.indicators as ta
from jesse.strategies import Strategy

class BTCMomentum(Strategy):
    """BTC动量策略"""

    def should_long(self) -> bool:
        return (
            self.price > self.ema(21) and
            self.rsi > 50 and
            self.macd[0] > self.macd[1]
        )

    def should_short(self) -> bool:
        return (
            self.price < self.ema(21) and
            self.rsi < 50 and
            self.macd[0] < self.macd[1]
        )

    def should_cancel_entry(self) -> bool:
        return True

    def go_long(self):
        entry = self.price
        stop = entry - self.atr * 2
        qty = utils.risk_to_qty(self.balance, 2, entry, stop)
        self.buy = qty, entry
        self.stop_loss = qty, stop
        self.take_profit = qty, entry + (entry - stop) * 3

    def go_short(self):
        entry = self.price
        stop = entry + self.atr * 2
        qty = utils.risk_to_qty(self.balance, 2, entry, stop)
        self.sell = qty, entry
        self.stop_loss = qty, stop
        self.take_profit = qty, entry - (stop - entry) * 3

    @property
    def ema(self, period=21):
        return ta.ema(self.candles, period)

    @property
    def rsi(self, period=14):
        return ta.rsi(self.candles, period)

    @property
    def macd(self):
        return ta.macd(self.candles)
```

### 3.3 Jesse优势

- **语法简洁**：策略代码量少
- **内置风控**：仓位管理、止损止盈
- **回测快速**：C扩展加速
- **实时交易**：支持Binance/OKX等

---

## 四、自研框架（CCXT + Backtrader）

### 4.1 CCXT统一接口

```python
# pip install ccxt
import ccxt

# CCXT支持100+交易所的统一API
exchange = ccxt.binance({
    'apiKey': 'your_key',
    'secret': 'your_secret',
    'enableRateLimit': True,
})

# 统一接口
ticker = exchange.fetch_ticker('BTC/USDT')
ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=500)
order = exchange.create_order('BTC/USDT', 'limit', 'buy', 0.01, 50000)
balance = exchange.fetch_balance()
positions = exchange.fetch_positions(['BTC/USDT:USDT'])
```

### 4.2 自研回测引擎核心

```python
import pandas as pd
import numpy as np

class SimpleBacktester:
    """轻量回测引擎"""

    def __init__(self, initial_capital=10000, fee_rate=0.0005):
        self.capital = initial_capital
        self.fee_rate = fee_rate
        self.position = 0
        self.trades = []

    def run(self, data, signals):
        """
        data: DataFrame with 'close'
        signals: Series with 1 (long), -1 (short), 0 (flat)
        """
        portfolio_value = []

        for i in range(1, len(data)):
            price = data['close'].iloc[i]
            signal = signals.iloc[i-1]  # 前一期信号

            # 平仓
            if self.position != 0 and signal != self.position:
                if self.position > 0:
                    pnl = (price - self.entry_price) * self.position_size
                else:
                    pnl = (self.entry_price - price) * self.position_size
                fee = abs(self.position_size) * price * self.fee_rate
                self.capital += pnl - fee
                self.trades.append({
                    'exit_date': data.index[i],
                    'pnl': pnl - fee,
                })
                self.position = 0

            # 开仓
            if signal != 0 and self.position == 0:
                self.position = signal
                self.position_size = self.capital * 0.95 / price  # 95%仓位
                self.entry_price = price
                fee = self.position_size * price * self.fee_rate
                self.capital -= fee

            # 记录组合价值
            if self.position != 0:
                if self.position > 0:
                    val = self.capital + (price - self.entry_price) * self.position_size
                else:
                    val = self.capital + (self.entry_price - price) * self.position_size
            else:
                val = self.capital

            portfolio_value.append(val)

        return pd.Series(portfolio_value, index=data.index[1:])
```

---

## 五、推荐选择

| 场景 | 推荐 | 原因 |
|------|------|------|
| **入门** | Freqtrade | 文档全、社区大、实盘支持 |
| **快速原型** | Jesse | 代码简洁、上手快 |
| **深度定制** | 自研+CCXT | 完全控制 |
| **ML策略** | Freqtrade FreqAI | 内置ML支持 |

---

## 六、信息源

| 来源 | 链接 |
|------|------|
| Freqtrade文档 | https://www.freqtrade.io/en/stable/ |
| Jesse文档 | https://docs.jesse.trade |
| CCXT文档 | https://docs.ccxt.com |
| FreqAI文档 | https://www.freqtrade.io/en/stable/freqai/ |

---

*下一报告: R12-BTC交易所API.md → Binance/OKX/Bybit REST+WebSocket*
