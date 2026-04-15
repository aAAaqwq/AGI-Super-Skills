# R12: BTC交易所API

> 学习日期: 2026-04-03 | 难度: ⭐⭐⭐⭐ 专业

---

## 一、API概览

### 1.1 API类型

| 类型 | 用途 | 延迟 | 限频 |
|------|------|------|------|
| **REST API** | 查询/下单 | 50-200ms | 10-1200次/分钟 |
| **WebSocket** | 实时行情/推送 | <10ms | 连接数限制 |
| **Fix协议** | 机构交易 | <1ms | 需申请 |

---

## 二、Binance API（最全）

### 2.1 REST API

```python
# pip install ccxt python-binance
import ccxt
import hmac
import hashlib
import requests
import time

# ===== 方式1: CCXT (推荐) =====
exchange = ccxt.binance({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET',
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',  # 使用合约
    }
})

# --- 行情API ---

# 获取Ticker
ticker = exchange.fetch_ticker('BTC/USDT')
print(f"BTC/USDT: {ticker['last']}")

# 获取K线
ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=500)
# [[timestamp, open, high, low, close, volume], ...]

# 获取深度
orderbook = exchange.fetch_order_book('BTC/USDT', limit=20)
print(f"买一: {orderbook['bids'][0]}")
print(f"卖一: {orderbook['asks'][0]}")

# 获取资金费率
funding = exchange.fetch_funding_rate('BTC/USDT:USDT')

# 获取持仓
positions = exchange.fetch_positions(['BTC/USDT:USDT'])

# --- 交易API ---

# 限价买入
order = exchange.create_limit_buy_order('BTC/USDT', 0.01, 50000)

# 市价买入
order = exchange.create_market_buy_order('BTC/USDT', 0.01)

# 合约做空
order = exchange.create_order(
    symbol='BTC/USDT:USDT',
    type='market',
    side='sell',
    amount=0.01,
)

# 设置杠杆
exchange.set_leverage(5, 'BTC/USDT:USDT')

# 设置止损
stop_order = exchange.create_order(
    symbol='BTC/USDT:USDT',
    type='STOP_MARKET',
    side='sell',
    amount=0.01,
    params={'stopPrice': 49000}
)

# 查询订单
order = exchange.fetch_order(order_id, 'BTC/USDT:USDT')

# 取消订单
exchange.cancel_order(order_id, 'BTC/USDT:USDT')

# 查询余额
balance = exchange.fetch_balance()
```

### 2.2 WebSocket（实时数据）

```python
# pip install websocket-client
import json
import websocket
import threading

class BinanceWebSocket:
    """Binance WebSocket 客户端"""

    # 现货WebSocket
    SPOT_WS = 'wss://stream.binance.com:9443/ws'

    # 合约WebSocket
    FUTURES_WS = 'wss://fstream.binance.com/ws'

    def __init__(self, is_futures=True):
        self.ws_url = self.FUTURES_WS if is_futures else self.SPOT_WS
        self.callbacks = {}

    def on_message(self, ws, message):
        data = json.loads(message)

        if 'e' in data:
            event_type = data['e']

            if event_type == 'kline':
                # K线数据
                k = data['k']
                print(f"K线: {k['s']} {k['i']} "
                      f"O:{k['o']} H:{k['h']} L:{k['l']} C:{k['c']}")

            elif event_type == 'depthUpdate':
                # 深度更新
                bids = data['b']
                asks = data['a']
                if bids:
                    print(f"买: {bids[0]}")
                if asks:
                    print(f"卖: {asks[0]}")

            elif event_type == 'aggTrade':
                # 成交数据
                print(f"成交: {data['s']} "
                      f"价格:{data['p']} 数量:{data['q']} "
                      f"方向:{'买' if data['m'] else '卖'}")

        if 'callback' in self.callbacks:
            self.callbacks['callback'](data)

    def on_error(self, ws, error):
        print(f"WebSocket Error: {error}")

    def on_close(self, ws, close_status, close_msg):
        print("WebSocket Closed")

    def on_open(self, ws):
        print("WebSocket Connected")

    def subscribe_kline(self, symbol='btcusdt', interval='1h'):
        """订阅K线"""
        ws = websocket.WebSocketApp(
            f"{self.ws_url}/{symbol}@kline_{interval}",
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()

    def subscribe_depth(self, symbol='btcusdt', speed='100ms'):
        """订阅深度"""
        ws = websocket.WebSocketApp(
            f"{self.ws_url}/{symbol}@depth@{speed}",
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()

    def subscribe_trades(self, symbol='btcusdt'):
        """订阅成交"""
        ws = websocket.WebSocketApp(
            f"{self.ws_url}/{symbol}@aggTrade",
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()

# 使用
bws = BinanceWebSocket(is_futures=True)
bws.subscribe_kline('btcusdt', '1m')
bws.subscribe_trades('btcusdt')
```

### 2.3 Binance API限频

| 接口类型 | 限频 | 说明 |
|----------|------|------|
| 下单 | 10次/秒 | 以order count计 |
| 查询订单 | 20次/秒 | 以weight计 |
| 行情 | 2400次/分钟 | 以weight计 |
| WebSocket连接 | 5个 | 单IP |
| WebSocket消息 | 5次/秒 | 单连接 |

---

## 三、OKX API

### 3.1 REST API

```python
import ccxt

okx = ccxt.okx({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET',
    'password': 'YOUR_PASSPHRASE',  # OKX特有的passphrase
    'enableRateLimit': True,
})

# 获取行情
ticker = okx.fetch_ticker('BTC/USDT:USDT')

# 获取K线
ohlcv = okx.fetch_ohlcv('BTC/USDT:USDT', '1h', limit=300)

# 设置杠杆
okx.set_leverage(5, 'BTC/USDT:USDT', params={'mgnMode': 'cross'})

# 开多
order = okx.create_order(
    symbol='BTC/USDT:USDT',
    type='market',
    side='buy',
    amount=0.01,
    params={'tdMode': 'cross'}  # cross=全仓, isolated=逐仓
)

# 开空
order = okx.create_order(
    symbol='BTC/USDT:USDT',
    type='market',
    side='sell',
    amount=0.01,
    params={'tdMode': 'cross'}
)
```

### 3.2 OKX特色API

```python
# 获取资金费率历史
funding_history = okx.fetch_funding_rate_history(
    'BTC/USDT:USDT', limit=100
)

# 获取持仓模式
# OKX支持双向持仓
okx.private_post_account_set_position_mode({
    'posMode': 'long_short_mode'  # 双向持仓
})

# 获取标记价格
mark_price = okx.fetch_mark_price('BTC/USDT:USDT')

# 获取资金费率
funding = okx.fetch_funding_rate('BTC/USDT:USDT')
```

---

## 四、Bybit API

```python
import ccxt

bybit = ccxt.bybit({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET',
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'}  # 永续合约
})

# 获取行情
ticker = bybit.fetch_ticker('BTC/USDT:USDT')

# 设置杠杆
bybit.set_leverage(5, 'BTC/USDT:USDT')

# 开仓
order = bybit.create_order(
    symbol='BTC/USDT:USDT',
    type='market',
    side='buy',
    amount=0.01,
)
```

---

## 五、统一交易框架

### 5.1 多交易所套利基础

```python
class MultiExchangeTrader:
    """多交易所统一接口"""

    def __init__(self, exchanges_config):
        self.exchanges = {}
        for name, config in exchanges_config.items():
            self.exchanges[name] = getattr(ccxt, name)(config)

    def get_best_price(self, symbol):
        """获取所有交易所的最优价格"""
        prices = {}
        for name, ex in self.exchanges.items():
            try:
                ticker = ex.fetch_ticker(symbol)
                prices[name] = {
                    'bid': ticker['bid'],
                    'ask': ticker['ask'],
                }
            except Exception as e:
                print(f"{name}: {e}")

        # 找最优买价和卖价
        best_bid = max(prices.items(), key=lambda x: x[1]['bid'])
        best_ask = min(prices.items(), key=lambda x: x[1]['ask'])

        spread = best_bid[1]['bid'] - best_ask[1]['ask']
        print(f"最优买入: {best_ask[0]} @ {best_ask[1]['ask']}")
        print(f"最优卖出: {best_bid[0]} @ {best_bid[1]['bid']}")
        print(f"套利空间: {spread:.2f} USDT ({spread/best_ask[1]['ask']*100:.3f}%)")

        return prices

    def execute_arbitrage(self, symbol, amount):
        """执行跨所套利"""
        prices = self.get_best_price(symbol)

        # 在低价交易所买入
        buy_exchange = min(prices.items(), key=lambda x: x[1]['ask'])
        buy_ex = self.exchanges[buy_exchange[0]]
        buy_order = buy_ex.create_market_buy_order(symbol, amount)

        # 在高价交易所卖出
        sell_exchange = max(prices.items(), key=lambda x: x[1]['bid'])
        sell_ex = self.exchanges[sell_exchange[0]]
        sell_order = sell_ex.create_market_sell_order(symbol, amount)

        return {
            'buy': {'exchange': buy_exchange[0], 'order': buy_order},
            'sell': {'exchange': sell_exchange[0], 'order': sell_order},
        }
```

---

## 六、API安全最佳实践

| 措施 | 说明 |
|------|------|
| **只开启必要权限** | 只开"交易"，不开"提现" |
| **IP白名单** | 绑定VPS的IP |
| **密钥轮换** | 定期更换API Key |
| **子账户** | 策略用子账户，隔离风险 |
| **监控告警** | 异常交易量/金额告警 |
| **环境变量** | 不硬编码密钥 |
| **日志审计** | 记录所有API调用 |

---

## 七、信息源

| 来源 | 链接 |
|------|------|
| Binance API | https://binance-docs.github.io/apidocs |
| OKX API | https://www.okx.com/docs-v5 |
| Bybit API | https://bybit-exchange.github.io/docs |
| CCXT | https://docs.ccxt.com |

---

*下一报告: R13-BTC数据源.md → CoinGecko/Glassnode/CryptoCompare*
