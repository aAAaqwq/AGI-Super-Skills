# Polymarket API详细命令

## Gamma API

### 市场发现
```bash
# 所有活跃市场(按交易量)
curl -s "https://gamma-api.polymarket.com/markets?active=true&closed=false&order=volume24hr&ascending=false&limit=100"

# 按tag筛选
curl -s "https://gamma-api.polymarket.com/markets?active=true&closed=false&tag=crypto&limit=20"

# 事件列表
curl -s "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=50"
```

### 搜索
```bash
# 搜索市场 (正确格式)
curl -s "https://gamma-api.polymarket.com/public-search?q=bitcoin&limit_per_type=10"
curl -s "https://gamma-api.polymarket.com/public-search?q=elon%20musk&limit_per_type=5"
curl -s "https://gamma-api.polymarket.com/public-search?q=bitcoin%20above&limit_per_type=10"
```

### Slug查询
```bash
# BTC日盘
curl -s "https://gamma-api.polymarket.com/events?slug=bitcoin-above-on-march-10"
curl -s "https://gamma-api.polymarket.com/events?slug=bitcoin-above-on-march-11"

# ETH日盘
curl -s "https://gamma-api.polymarket.com/events?slug=ethereum-above-on-march-10"

# SOL日盘
curl -s "https://gamma-api.polymarket.com/events?slug=solana-above-on-march-10"

# Gold月盘
curl -s "https://gamma-api.polymarket.com/events?slug=gold-gc-above-end-of-march"

# Elon推文盘
curl -s "https://gamma-api.polymarket.com/events?slug=elon-musk-of-tweets-march-8-march-10"
```

## CLOB API

### 价格
```bash
TOKEN_ID="从clobTokenIds获取"
curl -s "https://clob.polymarket.com/price?token_id=${TOKEN_ID}&side=buy"
curl -s "https://clob.polymarket.com/price?token_id=${TOKEN_ID}&side=sell"
```

### 订单簿
```bash
curl -s "https://clob.polymarket.com/book?token_id=${TOKEN_ID}"
```

### 价格历史
```bash
# 1小时间隔
curl -s "https://clob.polymarket.com/prices-history?market=${TOKEN_ID}&interval=1h"

# 1天间隔
curl -s "https://clob.polymarket.com/prices-history?market=${TOKEN_ID}&interval=1d"

# 返回格式: {"history": [{"t": 1772971238, "p": 0.9995}, ...]}
```

## Data API

### 持仓
```bash
WALLET="0x..."
curl -s "https://data-api.polymarket.com/positions?user=${WALLET}"
```

## 实用jq筛选

### 甜区扫描 (75-85¢)
```bash
curl -s "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=500" | \
jq -r '.[] | 
  if .outcomePrices then 
    (.outcomePrices | fromjson | .[0] | tonumber) as $yes 
    | select($yes >= 0.75 and $yes <= 0.85)
    | "\(.question[:70]) | Yes:\($yes)"
  else empty end'
```

### Crypto市场扫描
```bash
curl -s "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=500" | \
jq -r '.[] | select(.question | test("crypto|bitcoin|btc|eth|ethereum|solana"; "i")) | 
  "\(.question[:70]) | Yes:\(.outcomePrices) | Vol:\(.volume24hr/1000 | floor)k"'
```

### BTC "Above"类型市场
```bash
curl -s "https://gamma-api.polymarket.com/events?slug=bitcoin-above-on-march-10" | \
jq -r '.[] | .markets[] | 
  .outcomePrices as $p | 
  ($p | fromjson) as $prices |
  "$\($.question[30:40]) | Yes:\($prices[0]) | Vol:\((.volume | tonumber | floor))"'
```

## 已知限制

- **Search API**: 正确格式是 `?q=xxx`，不是 `?_s=xxx`
- **5min/15min盘**: API无法发现，需用browser扫描polymarket.com/markets
- **交易**: 需钱包签名，API只读
