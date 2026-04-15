# 高质量新闻源调研报告

**调研日期**: 2026-03-23  
**调研人**: Quant (量化交易AI)  
**目的**: 为量化交易系统提供实时、准确、结构化的新闻数据源

---

## 执行摘要

本报告调研了适用于量化交易的新闻源，按以下维度评估：
- **实时性**: 准实时或低延迟
- **准确性**: 权威来源
- **结构化**: 程序化处理便利度
- **覆盖范围**: 宏观/行业/加密货币/美股/中文

### 推荐优先级

| 优先级 | 数据源 | 类型 | 实时性 | 程序化难度 | 免费 |
|--------|--------|------|--------|------------|------|
| 🔴 P0 | CryptoCompare | 加密货币 | <1min | API简单 | 部分免费 |
| 🔴 P0 | CoinGecko API | 加密货币 | <1min | API简单 | 免费 |
| 🟡 P1 | NewsAPI | 综合 | <30min | API简单 | 免费 tier |
| 🟡 P1 | Yahoo Finance | 金融 | <5min | API简单 | 免费 |
| 🟢 P2 | RSS 聚合 | 综合 | 视源而定 | 中等 | 免费 |
| 🟢 P2 | Wolfram Alpha | 宏观 | <1h | API | 免费 tier |

---

## 一、加密货币新闻源

### 1. CryptoCompare News API ⭐⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **API端点** | `https://min-api.cryptocompare.com/data/v2/news/` |
| **更新频率** | 实时推送，每分钟数十条 |
| **数据格式** | JSON，包含title, body, source, categories, imageurl, url |
| **覆盖范围** | 全球加密货币新闻，来源包括CoinDesk, Bloomberg, Reuters等 |
| **API Key** | 需要免费API key（可申请） |
| **免费额度** | 足够个人/小团队使用 |
| **程序化难度** | ⭐ 低 — RESTful API，返回结构化JSON |

**技术实现**:
```bash
curl -s "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&api_key=YOUR_KEY"
```

**字段示例**:
```json
{
  "title": "Bitcoin Surges Past $72K",
  "body": "...",
  "source": "CoinDesk",
  "categories": "Bitcoin",
  "published_on": 1640000000
}
```

---

### 2. CoinGecko API (行情+新闻) ⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **API端点** | `https://api.coingecko.com/api/v3/` |
| **更新频率** | 实时价格，新闻视源而定 |
| **数据格式** | JSON |
| **覆盖范围** | 加密货币价格+基本信息，无新闻全文但有trending |
| **API Key** | 免费 tier 足够用 |
| **免费额度** | 10,000 calls/month (免费 tier) |
| **程序化难度** | ⭐ 低 |

**用途**: 补充价格数据+market sentiment

---

### 3. CoinMarketCap API ⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **API端点** | `https://pro-api.coinmarketcap.com/v1/` |
| **更新频率** | 实时 |
| **数据格式** | JSON |
| **覆盖范围** | 加密货币价格+market data |
| **API Key** | 需要（免费 tier 有额度） |
| **免费额度** | 10,000 calls/month |
| **程序化难度** | ⭐ 低 |

---

### 4. CryptoPanic / Cryptodoner ⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **API端点** | `https://cryptopanic.com/news/api/v1/posts/` |
| **更新频率** | 实时聚合 |
| **数据格式** | JSON |
| **覆盖范围** | 加密货币新闻聚合 |
| **API Key** | 需要注册 |
| **免费额度** | 有限 |
| **程序化难度** | ⭐ 低 |

---

### 5. BitcoinBlockHalf / BTC.com ⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **数据** | 链上数据+新闻聚合 |
| **覆盖范围** | BTC网络数据 |
| **程序化难度** | ⭐ 中等 |

---

## 二、宏观经济新闻源

### 6. NewsAPI (综合) ⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **API端点** | `https://newsapi.org/v2/` |
| **更新频率** | <30min |
| **数据格式** | JSON |
| **覆盖范围** | 全球新闻，可按category/business过滤 |
| **API Key** | 需要（免费 tier可用） |
| **免费额度** | 100 requests/day (免费 tier) |
| **程序化难度** | ⭐ 低 |

**技术实现**:
```bash
curl -s "https://newsapi.org/v2/top-headlines?category=business&apiKey=YOUR_KEY"
```

**局限**: 不支持商业化用途的完全免费调用

---

### 7. Yahoo Finance API ⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **API端点** | `https://query1.finance.yahoo.com/v8/finance/` |
| **更新频率** | <5min |
| **数据格式** | JSON |
| **覆盖范围** | 美股+宏观+加密货币价格 |
| **API Key** | 无需 |
| **免费额度** | 无限制 |
| **程序化难度** | ⭐ 极低 |

**技术实现**:
```bash
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?interval=1d"
```

---

### 8. FRED (Federal Reserve Economic Data) ⭐⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **API端点** | `https://api.stlouisfed.org/fred/` |
| **更新频率** | 日/周/月（视指标而定） |
| **数据格式** | JSON/CSV |
| **覆盖范围** | 美国宏观经济数据：GDP, CPI, 失业率, 利率等 |
| **API Key** | 需要免费API key |
| **免费额度** | 足够非高频使用 |
| **程序化难度** | ⭐ 低 |

**技术实现**:
```bash
curl -s "https://api.stlouisfed.org/fred/series/observations?series_id=GDP&api_key=YOUR_KEY"
```

---

### 9. TradingEconomics ⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **Web** | https://tradingeconomics.com/ |
| **更新频率** | 实时 |
| **数据格式** | JSON (API需付费) |
| **覆盖范围** | 全球宏观经济指标 |
| **程序化难度** | ⭐ 中等（网页可爬） |

---

## 三、美股新闻源

### 10. Alpha Vantage ⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **API端点** | `https://www.alphavantage.co/query` |
| **更新频率** | <15min |
| **数据格式** | JSON |
| **覆盖范围** | 美股+外汇+宏观经济 |
| **API Key** | 需要免费key |
| **免费额度** | 25 requests/day (免费 tier) |
| **程序化难度** | ⭐ 低 |

---

### 11. Finnhub ⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **API端点** | `https://finnhub.io/api/v1/` |
| **更新频率** | 实时 |
| **数据格式** | JSON |
| **覆盖范围** | 美股新闻+财报+舆情 |
| **API Key** | 需要免费key |
| **免费额度** | 足够小团队使用 |
| **程序化难度** | ⭐ 低 |

---

## 四、中文新闻源

### 12. 财新 (Caixin) ⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **数据** | 中文商业财经新闻 |
| **更新频率** | 实时 |
| **程序化难度** | ⭐⭐⭐ 中等（需爬虫） |
| **免费** | 部分免费 |

**技术实现**: 使用RSS或网页爬虫

---

### 13. 华尔街见闻 ⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **数据** | 中文金融资讯 |
| **更新频率** | 实时 |
| **程序化难度** | ⭐⭐⭐ 中等（需爬虫） |
| **免费** | 部分免费 |

---

### 14. 新浪财经 / 东方财富 ⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **数据** | A股+宏观经济数据 |
| **程序化难度** | ⭐⭐ 中等（有API但不稳定） |
| **免费** | 免费 |

---

## 五、Twitter/X 实时舆情

### 15. X API (Twitter) ⭐⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **API端点** | `https://api.twitter.com/2/` |
| **更新频率** | 实时流 |
| **数据格式** | JSON |
| **覆盖范围** | KOL推文、实时热点 |
| **API Key** | 需要付费订阅 |
| **程序化难度** | ⭐⭐ 中等 |

**替代方案**: 
- **Nitter** (开源Twitter前端，可爬)
- **Feedbin** (RSS化Twitter)
- **通过小data人工监控特定KOL**

---

## 六、专用交易信号源

### 16. Whale Alert ⭐⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **API端点** | `https://api.whale-alert.io/v1/` |
| **更新频率** | 实时（链上大额转账） |
| **数据格式** | JSON |
| **覆盖范围** | BTC/ETH大额链上转账 |
| **API Key** | 需要（免费 tier有有限额度） |
| **免费额度** | 约2000 calls/month |
| **程序化难度** | ⭐ 极低 |

**技术实现**:
```bash
curl -s "https://api.whale-alert.io/v1/transactions?api_key=YOUR_KEY&min_value=1000000"
```

**用途**: 检测鲸鱼异动，预警大幅波动

---

### 17. Glassnode / IntoTheBlock ⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **数据** | 链上指标（NUPL, MVRV, Exchange Flow等） |
| **更新频率** | 小时级 |
| **程序化难度** | ⭐⭐ 中等 |
| **免费** | 付费服务 |

---

## 七、RSS 聚合方案 (免费+自建)

### 18. RSSHub + Miniflux ⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **方案** | 自建RSS聚合器 |
| **数据源** | 任意RSS源 |
| **程序化难度** | ⭐⭐⭐ 中等（需部署） |
| **免费** | 完全免费 |

**推荐RSS源**:
- CoinDesk RSS: `https://www.coindesk.com/feed/`
- Bloomberg: `https://feeds.bloomberg.com/markets/news.rss`
- Reuters: `https://www.reutersagency.com/feed/`

---

## 八、综合推荐方案

### 方案A: 轻量级（免费为主）

| 组件 | 数据源 | 用途 |
|------|--------|------|
| 价格数据 | Yahoo Finance / Binance API | 实时价格 |
| 加密新闻 | CryptoCompare (申请key) | 行业新闻 |
| 宏观事件 | TradingEconomics (网页爬) | 关键日程 |
| 鲸鱼监控 | Whale Alert (免费key) | 链上大额转账 |

**月成本**: $0

---

### 方案B: 专业级（付费）

| 组件 | 数据源 | 成本 |
|------|--------|------|
| 综合新闻 | NewsAPI Pro | ~$50/月 |
| 加密数据 | CryptoCompare Pro | ~$100/月 |
| 链上数据 | Glassnode | ~$30/月 |
| Twitter | X API Basic | ~$100/月 |

**月成本**: ~$280/月

---

## 九、技术实现路径

### 1. 即插即用脚本 (优先级最高)

```bash
# CryptoCompare 新闻获取脚本
#!/bin/bash
# 保存为 scripts/news_cryptocompare.sh
API_KEY="${1:-YOUR_CRYPTCOMPARE_KEY}"
curl -s "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&api_key=$API_KEY" | \
  jq '[.Data[] | {title, source, categories, published_on}]'
```

### 2. Whale Alert 集成

```bash
# 链上大额转账监控
curl -s "https://api.whale-alert.io/v1/transactions?api_key=$WHALE_KEY&min_value=500000" | \
  jq '[.transactions[] | {from, to, amount, symbol, timestamp}]'
```

### 3. RSS 聚合

```bash
# 组合多个RSS源
#!/bin/bash
echo "=== CoinDesk ==="
curl -s "https://www.coindesk.com/feed/" | grep -o '<title>[^<]*</title>' | head -5
echo "=== Reuters ==="
curl -s "https://www.reutersagency.com/feed/?best-topics=biz-finance" | grep -o '<title>[^<]*</title>' | head -5
```

---

## 十、下一步行动

| 优先级 | 任务 | 负责人 | 预估 |
|--------|------|--------|------|
| 🔴 P0 | 申请 CryptoCompare API Key | Quant | 10min |
| 🔴 P0 | 申请 Whale Alert API Key | Quant | 10min |
| 🟡 P1 | 重写 news_monitor.sh 使用 CryptoCompare | Quant | 2h |
| 🟡 P1 | 接入 Whale Alert 链上监控 | Quant+Code | 4h |
| 🟢 P2 | 搭建 RSSHub 聚合器 | 小data | 1天 |
| 🟢 P2 | 接入 X/Twitter KOL 监控 | 小data | 1天 |

---

## 附录：API Key 申请链接

| 服务 | 申请链接 |
|------|----------|
| CryptoCompare | https://www.cryptocompare.com/cryptopian/api-keys |
| Whale Alert | https://whale-alert.io/ |
| NewsAPI | https://newsapi.org/register |
| Alpha Vantage | https://www.alphavantage.co/support/#api-key |
| FRED | https://fred.stlouisfed.org/docs/api/api_key.html |
| Finnhub | https://finnhub.io/ |

---

*报告生成: Quant (量化交易AI)*  
*最后更新: 2026-03-23*
