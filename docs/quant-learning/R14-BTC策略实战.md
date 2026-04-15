# R14: BTC策略实战

> 学习日期: 2026-04-03 | 难度: ⭐⭐⭐⭐ 进阶

---

## 一、策略分类

```
BTC量化策略实战图谱:

├── 趋势策略
│   ├── 动量策略 (Momentum)
│   ├── 均线策略 (MA Cross)
│   └── 突破策略 (Breakout)
│
├── 回归策略
│   ├── 均值回归 (Mean Reversion)
│   ├── 网格交易 (Grid Trading)
│   └── 布林带策略 (Bollinger Band)
│
├── 套利策略
│   ├── 期现套利 (Spot-Futures)
│   ├── 跨交易所套利 (Cross-Exchange)
│   ├── 资金费率套利 (Funding Rate)
│   └── 三角套利 (Triangular)
│
└── 做市策略
    ├── 网格做市 (Grid Market Making)
    └── Avellaneda-Stoikov 做市
```

---

## 二、网格交易

### 2.1 策略逻辑

在价格区间内等距设置多档买卖单，价格下跌自动买入、上涨自动卖出。

```
网格示意:

卖 ← 70000 ─── 卖出 ─── (+500)
    69500 ─── 卖出 ─── (+500)
    69000 ─── 卖出 ─── (+500)
    68500 ─── 卖出 ───
    ═════════════════  当前价格 68200
    67500 ─── 买入 ───
    67000 ─── 买入 ─── (+500)
    66500 ─── 买入 ─── (+500)
买 ← 66000 ─── 买入 ─── (+500)
```

### 2.2 Python实现

```python
import ccxt
import numpy as np
import time

class GridTrader:
    """网格交易策略"""

    def __init__(self, exchange, symbol, grid_range, grid_num, total_investment):
        """
        exchange: ccxt交易所实例
        symbol: 如 'BTC/USDT'
        grid_range: (下限, 上限) 价格区间
        grid_num: 网格数量
        total_investment: 总投资金额(USDT)
        """
        self.exchange = exchange
        self.symbol = symbol
        self.lower, self.upper = grid_range
        self.grid_num = grid_num
        self.total_investment = total_investment

        # 计算网格参数
        self.grid_spacing = (self.upper - self.lower) / grid_num
        self.grid_levels = np.linspace(self.lower, self.upper, grid_num + 1)
        self.order_size = total_investment / grid_num / ((self.lower + self.upper) / 2)

        self.orders = {}  # 网格订单追踪

    def place_initial_orders(self):
        """放置初始网格订单"""
        current_price = self.exchange.fetch_ticker(self.symbol)['last']

        print(f"当前价格: {current_price}")
        print(f"网格区间: {self.lower} - {self.upper}")
        print(f"网格间距: {self.grid_spacing:.2f}")
        print(f"每格数量: {self.order_size:.6f} BTC")

        for i, level in enumerate(self.grid_levels):
            if level < current_price:
                # 低于当前价 → 挂买单
                order = self.exchange.create_limit_buy_order(
                    self.symbol, self.order_size, level
                )
                self.orders[order['id']] = {
                    'type': 'buy', 'level': level, 'index': i
                }
                print(f"  买单: {level:.2f} x {self.order_size:.6f}")

            elif level > current_price:
                # 高于当前价 → 挂卖单
                order = self.exchange.create_limit_sell_order(
                    self.symbol, self.order_size, level
                )
                self.orders[order['id']] = {
                    'type': 'sell', 'level': level, 'index': i
                }
                print(f"  卖单: {level:.2f} x {self.order_size:.6f}")

    def check_and_rebalance(self):
        """检查成交并重新挂单"""
        open_orders = self.exchange.fetch_open_orders(self.symbol)
        open_ids = {o['id'] for o in open_orders}

        # 找到已成交的订单
        filled = [oid for oid in self.orders if oid not in open_ids]

        for oid in filled:
            order_info = self.orders[oid]

            if order_info['type'] == 'buy':
                # 买单成交 → 在上一格挂卖单
                sell_level = order_info['level'] + self.grid_spacing
                if sell_level <= self.upper:
                    new_order = self.exchange.create_limit_sell_order(
                        self.symbol, self.order_size, sell_level
                    )
                    self.orders[new_order['id']] = {
                        'type': 'sell', 'level': sell_level
                    }
                    print(f"✅ 买入成交@{order_info['level']:.2f} → 挂卖@{sell_level:.2f}")
                    print(f"   预期利润: {self.grid_spacing * self.order_size:.2f} USDT")

            elif order_info['type'] == 'sell':
                # 卖单成交 → 在下一格挂买单
                buy_level = order_info['level'] - self.grid_spacing
                if buy_level >= self.lower:
                    new_order = self.exchange.create_limit_buy_order(
                        self.symbol, self.order_size, buy_level
                    )
                    self.orders[new_order['id']] = {
                        'type': 'buy', 'level': buy_level
                    }
                    print(f"✅ 卖出成交@{order_info['level']:.2f} → 挂买@{buy_level:.2f}")

            # 清理已成交订单
            del self.orders[oid]

    def run(self, interval=60):
        """运行网格"""
        self.place_initial_orders()

        while True:
            try:
                self.check_and_rebalance()
                time.sleep(interval)
            except KeyboardInterrupt:
                print("停止网格交易")
                self.cancel_all()
                break
            except Exception as e:
                print(f"错误: {e}")
                time.sleep(30)

    def cancel_all(self):
        """撤销所有订单"""
        open_orders = self.exchange.fetch_open_orders(self.symbol)
        for order in open_orders:
            self.exchange.cancel_order(order['id'], self.symbol)
        print(f"已撤销 {len(open_orders)} 个订单")
```

---

## 三、均值回归策略

### 3.1 布林带均值回归

```python
import pandas as pd
import numpy as np

class BollingerReversion:
    """布林带均值回归策略"""

    def __init__(self, bb_period=20, bb_std=2.0, rsi_period=14,
                 rsi_oversold=30, rsi_overbought=70):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    def generate_signals(self, df):
        """
        df: DataFrame with 'close', 'volume'
        返回: signals Series (1=long, -1=short, 0=flat)
        """
        # 布林带
        df['ma'] = df['close'].rolling(self.bb_period).mean()
        df['std'] = df['close'].rolling(self.bb_period).std()
        df['upper'] = df['ma'] + self.bb_std * df['std']
        df['lower'] = df['ma'] - self.bb_std * df['std']

        # RSI
        delta = df['close'].diff()
        gain = delta.clip(lower=0).rolling(self.rsi_period).mean()
        loss = (-delta).clip(lower=0).rolling(self.rsi_period).mean()
        df['rsi'] = 100 - 100 / (1 + gain / loss)

        # 信号生成
        signals = pd.Series(0, index=df.index)

        # 做多：价格触及下轨 + RSI超卖
        buy_cond = (
            (df['close'] <= df['lower']) &
            (df['rsi'] < self.rsi_oversold)
        )

        # 做空：价格触及上轨 + RSI超买
        sell_cond = (
            (df['close'] >= df['upper']) &
            (df['rsi'] > self.rsi_overbought)
        )

        # 出场：价格回归中轨
        exit_long = df['close'] >= df['ma']
        exit_short = df['close'] <= df['ma']

        position = 0
        for i in range(len(df)):
            if position == 0:
                if buy_cond.iloc[i]:
                    signals.iloc[i] = 1
                    position = 1
                elif sell_cond.iloc[i]:
                    signals.iloc[i] = -1
                    position = -1
            elif position == 1 and exit_long.iloc[i]:
                signals.iloc[i] = 0
                position = 0
            elif position == -1 and exit_short.iloc[i]:
                signals.iloc[i] = 0
                position = 0

        return signals
```

---

## 四、动量策略

### 4.1 多时间框架动量

```python
class MultiTFMomentum:
    """多时间框架动量策略"""

    def __init__(self, fast_ema=9, slow_ema=21, trend_ema=50):
        self.fast = fast_ema
        self.slow = slow_ema
        self.trend = trend_ema

    def generate_signals(self, df_1h, df_4h=None):
        """
        df_1h: 1小时数据（交易级别）
        df_4h: 4小时数据（趋势方向）
        """
        df = df_1h.copy()

        # EMA
        df['ema_fast'] = df['close'].ewm(span=self.fast).mean()
        df['ema_slow'] = df['close'].ewm(span=self.slow).mean()
        df['ema_trend'] = df['close'].ewm(span=self.trend).mean()

        # ADX（趋势强度）
        plus_dm = df['high'].diff().clip(lower=0)
        minus_dm = (-df['low'].diff()).clip(lower=0)
        tr = pd.DataFrame({
            'hl': df['high'] - df['low'],
            'hc': (df['high'] - df['close'].shift(1)).abs(),
            'lc': (df['low'] - df['close'].shift(1)).abs()
        }).max(axis=1)

        atr = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        df['adx'] = dx.rolling(14).mean()

        # 信号
        signals = pd.Series(0, index=df.index)

        long_cond = (
            (df['ema_fast'] > df['ema_slow']) &  # 快线上穿慢线
            (df['close'] > df['ema_trend']) &      # 高于趋势线
            (df['adx'] > 25)                        # 趋势足够强
        )

        short_cond = (
            (df['ema_fast'] < df['ema_slow']) &
            (df['close'] < df['ema_trend']) &
            (df['adx'] > 25)
        )

        signals[long_cond] = 1
        signals[short_cond] = -1

        return signals
```

---

## 五、期现套利

### 5.1 策略逻辑

利用永续合约与现货的价差获利，同时做多现货+做空合约（或反向），赚取资金费率。

```
期现套利流程:

1. 买入1 BTC 现货 @ $60,000
2. 做空1 BTC 合约 @ $60,050 (合约通常溢价)
3. 每日收取资金费率 (通常0.01-0.03%)
4. 价差收敛时平仓获利

利润来源:
- 资金费率: 0.01% × 3次/天 × 365天 ≈ 10.95%/年
- 基差收敛: 合约到期/价差收敛的利润
```

### 5.2 Python实现

```python
class SpotFuturesArb:
    """期现套利"""

    def __init__(self, exchange):
        self.exchange = exchange
        self.spot_symbol = 'BTC/USDT'
        self.futures_symbol = 'BTC/USDT:USDT'

    def check_opportunity(self):
        """检查套利机会"""
        spot_price = self.exchange.fetch_ticker(self.spot_symbol)['last']
        futures_price = self.exchange.fetch_ticker(self.futures_symbol)['last']
        funding_rate = self.exchange.fetch_funding_rate(self.futures_symbol)['fundingRate']

        basis = futures_price - spot_price
        basis_pct = basis / spot_price * 100

        print(f"现货: ${spot_price:.2f}")
        print(f"合约: ${futures_price:.2f}")
        print(f"基差: ${basis:.2f} ({basis_pct:.3f}%)")
        print(f"资金费率: {funding_rate*100:.4f}%")

        # 判断方向
        if basis_pct > 0.1:  # 合约溢价 > 0.1%
            return 'long_spot_short_futures'
        elif basis_pct < -0.1:  # 现货溢价
            return 'short_spot_long_futures'
        return None

    def execute(self, direction, amount_btc=0.01):
        """执行套利"""
        if direction == 'long_spot_short_futures':
            # 买入现货
            spot_order = self.exchange.create_market_buy_order(
                self.spot_symbol, amount_btc
            )
            # 做空合约
            futures_order = self.exchange.create_order(
                symbol=self.futures_symbol,
                type='market',
                side='sell',
                amount=amount_btc,
            )
            print(f"✅ 买入现货 + 做空合约")

        return {
            'spot_order': spot_order,
            'futures_order': futures_order,
        }
```

### 5.3 预期收益

| 市场状态 | 资金费率 | 年化收益 | 风险 |
|----------|----------|----------|------|
| 牛市 | 正(多头付费) | 15-30% | 合约溢价收窄 |
| 熊市 | 负(空头付费) | 10-20% | 需反向操作 |
| 震荡 | 接近0 | 5-10% | 较低 |

---

## 六、跨交易所套利

```python
class CrossExchangeArb:
    """跨交易所套利"""

    def __init__(self, exchanges):
        self.exchanges = exchanges  # {name: ccxt_instance}

    def scan_opportunities(self, symbol='BTC/USDT'):
        """扫描套利机会"""
        prices = {}
        for name, ex in self.exchanges.items():
            try:
                ticker = ex.fetch_ticker(symbol)
                prices[name] = {
                    'bid': ticker['bid'],
                    'ask': ticker['ask'],
                    'timestamp': ticker['timestamp']
                }
            except:
                continue

        opportunities = []
        for buy_ex, buy_data in prices.items():
            for sell_ex, sell_data in prices.items():
                if buy_ex == sell_ex:
                    continue

                spread = sell_data['bid'] - buy_data['ask']
                spread_pct = spread / buy_data['ask'] * 100

                # 扣除手续费（双面）
                fee = 0.1 * 2  # Maker 0.1% × 2
                net_spread = spread_pct - fee

                if net_spread > 0.02:  # 净利润 > 0.02%
                    opportunities.append({
                        'buy_exchange': buy_ex,
                        'sell_exchange': sell_ex,
                        'buy_price': buy_data['ask'],
                        'sell_price': sell_data['bid'],
                        'spread_pct': spread_pct,
                        'net_spread': net_spread,
                    })

        return sorted(opportunities, key=lambda x: -x['net_spread'])
```

---

## 七、策略选择建议

| 策略 | 资金门槛 | 风险 | 年化预期 | 推荐度 |
|------|----------|------|----------|--------|
| 网格交易 | $1,000+ | 中 | 10-30% | ⭐⭐⭐⭐ |
| 均值回归 | $500+ | 中 | 15-40% | ⭐⭐⭐ |
| 动量策略 | $500+ | 中高 | 20-100% | ⭐⭐⭐ |
| 期现套利 | $5,000+ | 低 | 10-25% | ⭐⭐⭐⭐⭐ |
| 跨所套利 | $10,000+ | 低 | 5-15% | ⭐⭐⭐ |

---

*下一报告: R15-机器学习在量化中的应用.md → XGBoost/LSTM/Transformer*
