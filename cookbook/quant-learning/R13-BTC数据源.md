# R13: BTC数据源

> 学习日期: 2026-04-03 | 难度: ⭐⭐ 基础

---

## 一、数据源对比

| 数据源 | 类型 | 数据范围 | 免费 | 延迟 | 适合 |
|--------|------|----------|------|------|------|
| **CCXT** | 交易数据 | 行情/交易/持仓 | ✅ | 实时 | 交易策略 |
| **CoinGecko** | 市场数据 | 价格/市值/交易量 | ✅(有限) | 1-5min | 市场分析 |
| **Glassnode** | 链上数据 | 全套链上指标 | ⚠️有限 | 日/周 | 链上分析 |
| **CryptoCompare** | 综合数据 | 价格/社交/链上 | ✅(有限) | 实时 | 综合 |
| **TradingView** | 技术分析 | 价格+指标 | ✅ | 实时 | 可视化 |
| **Blockchain.com** | 基础链上 | 交易/地址/算力 | ✅ | 实时 | 基础链上 |
| **Dune Analytics** | 自定义查询 | 链上任意数据 | ✅ | 分钟级 | 深度分析 |
| **CoinMetrics** | 机构级 | 全套 | ⚠️收费 | 日级 | 研究 |

---

## 二、免费数据获取

### 2.1 CoinGecko（推荐入门）

```python
# pip install pycoingecko
from pycoingecko import CoinGeckoAPI
import pandas as pd

cg = CoinGeckoAPI()

# BTC当前价格
price = cg.get_price(ids='bitcoin', vs_currencies='usd')
print(f"BTC: ${price['bitcoin']['usd']}")

# 历史价格（最多365天）
market_data = cg.get_coin_market_chart_by_id(
    id='bitcoin',
    vs_currency='usd',
    days=365
)

# 转为DataFrame
prices = pd.DataFrame(market_data['prices'], columns=['timestamp', 'price'])
prices['timestamp'] = pd.to_datetime(prices['timestamp'], unit='ms')
prices.set_index('timestamp', inplace=True)

volumes = pd.DataFrame(market_data['total_volumes'], columns=['timestamp', 'volume'])
volumes['timestamp'] = pd.to_datetime(volumes['timestamp'], unit='ms')

# 市值排行
top_coins = cg.get_coins_markets(
    vs_currency='usd',
    order='market_cap_desc',
    per_page=100,
    page=1
)
df_top = pd.DataFrame(top_coins)
print(df_top[['name', 'current_price', 'market_cap', 'total_volume']].head(10))

# 趋势币种
trending = cg.get_search_trending()
```

### 2.2 CryptoCompare

```python
# pip install cryptocompare
import cryptocompare

# 获取BTC价格
price = cryptocompare.get_price('BTC', 'USD')
print(price)

# 历史K线
hist = cryptocompare.get_historical_price_hour(
    'BTC', 'USD', limit=720, exchange='Binance'
)
df = pd.DataFrame(hist)
df['time'] = pd.to_datetime(df['time'], unit='s')

# 日K线
hist_daily = cryptocompare.get_historical_price_day(
    'BTC', 'USD', limit=365
)
```

### 2.3 Blockchain.com API

```python
import requests
import pandas as pd

class BlockchainData:
    """区块链基础数据"""

    BASE = 'https://blockchain.info'

    def get_blockchain_stats(self):
        """区块链统计"""
        r = requests.get(f'{self.BASE}/stats')
        data = r.json()
        return {
            'hash_rate': data.get('hash_rate'),
            'difficulty': data.get('difficulty'),
            'total_btc': data.get('totalbc'),
            'n_tx': data.get('n_tx'),  # 交易数
            'n_unique_addresses': data.get('n_unique_addresses'),
        }

    def get_price_history(self, timespan='1year'):
        """价格历史"""
        r = requests.get(f'{self.BASE}/charts/market-price',
                        params={'timespan': timespan, 'format': 'json'})
        data = r.json()
        df = pd.DataFrame(data['values'])
        df['x'] = pd.to_datetime(df['x'], unit='ms')
        return df

    def get_transaction_volume(self, timespan='1year'):
        """交易量历史"""
        r = requests.get(f'{self.BASE}/charts/estimated-transaction-volume-usd',
                        params={'timespan': timespan, 'format': 'json'})
        return r.json()
```

### 2.4 Binance公开数据（免费CSV）

```python
# Binance提供免费的Historical Data
# https://data.binance.vision/

# 直接下载CSV
import pandas as pd

# 下载BTC/USDT 1小时K线
url = 'https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2024-01.zip'

# 列名
columns = [
    'open_time', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'trades', 'taker_buy_volume',
    'taker_buy_quote_volume', 'ignore'
]

df = pd.read_csv(url, names=columns)
df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df.set_index('open_time', inplace=True)

# 包含所有历史月份
# 现货: data/spot/monthly/klines/BTCUSDT/1h/
# 合约: data/futures/um/monthly/klines/BTCUSDT/1h/
# 深度: data/futures/um/monthly/bookDepth/BTCUSDT/
# Ticker: data/futures/um/monthly/ticker/BTCUSDT/
```

---

## 三、付费/高级数据源

### 3.1 Glassnode

```python
# API: https://api.glassnode.com/v1/metrics/
# 需要 API Key (免费版有限)

import requests
import pandas as pd

class GlassnodeData:
    def __init__(self, api_key):
        self.api_key = api_key

    def get(self, endpoint, asset='BTC', interval='24h'):
        url = f'https://api.glassnode.com/v1/metrics/{endpoint}'
        r = requests.get(url, params={
            'a': asset, 'i': interval, 'api_key': self.api_key
        })
        df = pd.DataFrame(r.json())
        df['t'] = pd.to_datetime(df['t'], unit='s')
        df.set_index('t', inplace=True)
        return df

    # 常用指标
    def active_addresses(self):
        return self.get('addresses/active_count')

    def exchange_balance(self):
        return self.get('distribution/balance_exchanges')

    def whale_balance(self):
        return self.get('distribution/balance_1kplus_addresses')

    def nupl(self):
        return self.get('indicators/nupl')

    def sopr(self):
        return self.get('indicators/sopr')

    def mvrv(self):
        return self.get('market/mvrv')

    def stock_to_flow(self):
        return self.get('indicators/stock_to_flow_ratio')

    def mining_revenue(self):
        return self.get('mining/revenue_sum')
```

**Glassnode免费指标（无需API Key）：**
- 市场价格、市值
- 交易量
- 活跃地址数
- 部分基础链上指标

### 3.2 CryptoQuant

```python
# https://cryptoquant.com/
# 专注交易所流入流出数据

class CryptoQuantData:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base = 'https://api.cryptoquant.com/v1'

    def get_exchange_inflow(self, exchange='binance'):
        """交易所流入"""
        url = f'{self.base}/btc/exchange-flows/inflow'
        r = requests.get(url, params={
            'exchange': exchange,
            'window': 'day',
            'api_key': self.api_key
        })
        return r.json()

    def get_exchange_outflow(self, exchange='binance'):
        """交易所流出"""
        url = f'{self.base}/btc/exchange-flows/outflow'
        return requests.get(url, params={
            'exchange': exchange,
            'api_key': self.api_key
        }).json()

    def get_reserve(self, exchange='binance'):
        """交易所储备"""
        url = f'{self.base}/btc/exchange-flows/reserve'
        return requests.get(url, params={
            'exchange': exchange,
            'api_key': self.api_key
        }).json()
```

---

## 四、社交媒体数据

### 4.1 恐惧贪婪指数

```python
def get_fear_greed():
    """加密恐惧贪婪指数"""
    import requests
    r = requests.get('https://api.alternative.me/fng/?limit=30&format=json')
    data = r.json()['data']
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='s')
    df['value'] = df['value'].astype(int)
    return df
```

### 4.2 搜索热度（Google Trends替代）

```python
# pip install pytrends
from pytrends.request import TrendReq

pytrends = TrendReq(hl='en-US', tz=360)
pytrends.build_payload(['Bitcoin'], cat=0, timeframe='today 12-m')
interest = pytrends.interest_over_time()

# BTC搜索热度与价格的相关性分析
# 搜索热度飙升 → 通常对应价格顶部
```

---

## 五、数据管理最佳实践

### 5.1 数据缓存架构

```python
import os
import pandas as pd
from datetime import datetime, timedelta
import time

class DataCache:
    """加密数据缓存管理"""

    def __init__(self, cache_dir='./crypto_data'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_or_fetch(self, key, fetch_fn, max_age_hours=1):
        """缓存读取或获取"""
        cache_file = f'{self.cache_dir}/{key}.parquet'

        if os.path.exists(cache_file):
            age = (datetime.now() - datetime.fromtimestamp(
                os.path.getmtime(cache_file)))
            if age < timedelta(hours=max_age_hours):
                return pd.read_parquet(cache_file)

        # 获取新数据
        df = fetch_fn()
        df.to_parquet(cache_file)
        return df
```

### 5.2 数据更新脚本

```bash
# cron每日更新
# 0 */4 * * * cd /path/to/bot && python update_data.py
```

---

## 六、推荐组合

| 用途 | 免费方案 | 付费方案 |
|------|----------|----------|
| **行情数据** | CCXT + Binance Data | CoinAPI |
| **链上数据** | Blockchain.com | Glassnode Pro |
| **情绪数据** | Fear&Greed + X | Santiment |
| **综合** | CoinGecko + CryptoCompare | CoinMetrics |

---

*下一报告: R14-BTC策略实战.md → 网格交易/均值回归/动量/期现套利*
