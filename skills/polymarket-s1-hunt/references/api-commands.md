# S1扫描API命令

## BTC 日盘

```bash
# March N
curl -s "https://gamma-api.polymarket.com/events?slug=bitcoin-above-on-march-N" | \
  jq -r '.[] | .markets[] | 
    .outcomePrices as $p | 
    ($p | fromjson) as $prices |
    "$\($.question[30:40]) | Yes:\($prices[0]) | Vol:\((.volume | tonumber | floor))"'
```

## ETH 日盘

```bash
curl -s "https://gamma-api.polymarket.com/events?slug=ethereum-above-on-march-N"
curl -s "https://gamma-api.polymarket.com/events?slug=ethereum-above-on-march-$((N+1))"
```

## SOL 日盘

```bash
curl -s "https://gamma-api.polymarket.com/events?slug=solana-above-on-march-N"
curl -s "https://gamma-api.polymarket.com/events?slug=solana-above-on-march-$((N+1))"
```

## Gold 月盘

```bash
curl -s "https://gamma-api.polymarket.com/events?slug=gold-gc-above-end-of-march"
```

## 1h/4h Markets

```bash
# 4h
curl -s "https://gamma-api.polymarket.com/public-search?q=bitcoin%20up%20down%204h&limit_per_type=5"

# 1h/5m
curl -s "https://gamma-api.polymarket.com/public-search?q=bitcoin%20up%20down%205m%2015m&limit_per_type=5"
```

## Weekly

```bash
curl -s "https://gamma-api.polymarket.com/public-search?q=top%20performing%20crypto%20week&limit_per_type=5"
```

## Binance价格

```bash
curl -s --max-time 10 'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT'
curl -s --max-time 10 'https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT'
curl -s --max-time 10 'https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT'
curl -s --max-time 10 'https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT'
```
