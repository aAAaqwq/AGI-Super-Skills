# Polymarket API

**用途**: Polymarket API调用、市场扫描、价格获取

## 核心API

### Gamma API
```bash
# 活跃市场
curl -s "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100"

# 搜索 (✅ 正确格式: ?q=xxx)
curl -s "https://gamma-api.polymarket.com/public-search?q=bitcoin&limit_per_type=10"

# 按slug查询
curl -s "https://gamma-api.polymarket.com/events?slug=bitcoin-above-on-march-10"
```

### CLOB API
```bash
# 实时价格 (需token_id)
curl -s "https://clob.polymarket.com/price?token_id=${TOKEN_ID}&side=buy"

# 订单簿
curl -s "https://clob.polymarket.com/book?token_id=${TOKEN_ID}"

# 价格历史
curl -s "https://clob.polymarket.com/prices-history?market=${TOKEN_ID}&interval=1h"
```

### Data API
```bash
# 持仓查询
curl -s "https://data-api.polymarket.com/positions?user=${WALLET}"
```

## 关键字段

| 字段 | 说明 |
|------|------|
| `clobTokenIds[0]` | Yes token_id |
| `outcomePrices[0]` | Yes价格 |
| `volume24hr` | 24h交易量 |
| `endDate` | 结算时间 |

## 已知限制
- Search: `?q=xxx`，不是 `?_s=xxx`
- 5min/15min盘: 需browser

---
详见 `references/api-commands.md`
