# R6: 顶尖数据源全景

> 2026-05-23 | 来源: 48次 web_search + 2次 web_extract

## 一、替代数据(Alt Data)全景

| 类型 | 代表平台 | Alpha衰减 | 成本/年 | 最佳市场 |
|------|---------|----------|--------|---------|
| 卫星图像 | Orbital Insight | 3-6月 | $50K-200K | 大宗商品/零售 |
| 信用卡 | Second Measure(Bloomberg) | 2-4月 | $100K-300K | 零售股 |
| 网页流量 | SimilarWeb | 6-12月 | $2K-240K | 电商/SaaS |
| APP下载 | Sensor Tower | 6-12月 | $12K-120K | 社交/游戏 |
| 地理位置 | Placer.ai | 3-6月 | $25K-100K | 零售/旅游 |
| 供应链 | Panjiva(S&P Global) | 6-12月 | $1K-50K | 制造/贸易 |

**对加密市场**：替代数据直接Alpha有限，但可追踪CEX/DEX流量、加密钱包APP下载量（散户入场信号）。

---

## 二、加密专属数据源（核心！）

### 链上数据
- **Glassnode** — MVRV/SOPR/NUPL/Hash Ribbon | Pro $39/月 | ★★★★★
- **CoinMetrics** — 学术级数据质量 | Pro $50-500/月 | ★★★★
- **Dune Analytics** — SQL直接查询原始链上，最灵活 | Pro $29/月 | ★★★★★
- **Token Terminal** — 加密"Bloomberg"，协议基本面 | Pro $49/月 | ★★★★

### DEX数据
- **DeFi Llama** — 完全免费，无需API Key | TVL/Volume/APY | ★★★★★
- **The Graph** — GraphQL查询DeFi原始事件 | 免费 | ★★★★

### 社交情绪
- **Santiment** — 链上+社交融合最强 | Pro $49/月 | ★★★★★
- **CryptoQuant** — Exchange Flow最强短期Alpha | Pro $29/月 | ★★★★★
- **LunarCrush** — Galaxy Score/AltRank | Pro $99/月 | ★★★★

### Whale追踪
- **Arkham Intelligence** — 实体去匿名化独一无二 | 免费/定制 | ★★★★★
- **Whale Alert** — >$500K链上转账实时监控 | Pro $99/月 | ★★★

### 衍生品
- **Coinglass** — OI/Funding/Liquidation/L-S Ratio | Pro $49/月 | ★★★★★
- **Laevitas** — 期权/波动率曲面/Deribit | Pro $29/99/月 | ★★★★

### MEV/Mempool
- **Flashbots** — MEV-Boost数据，免费开源 | ★★★★★
- **Blocknative** — 实时mempool监控+Gas预测 | Pro $99-499/月 | ★★★★

---

## 三、宏观数据API

### 免费
- **FRED** — GDP/CPI/PCE/非农/DXY/M2 | `fredapi` Python | ★★★★
- **Yahoo Finance** — yfinance跨资产 | ★★★
- **GDPNow(Atlanta Fed)** — 实时GDP预测，领先官方4-6周 | ★★★★

### 中国专属
- **Wind** — ¥30K-100K+/年，A股全覆盖，机构标配 | ★★★★★
- **同花顺iFinD** — ¥5K-50K/年，Python API友好 | ★★★★
- **AKShare** — 完全免费开源，东方财富/新浪数据 | ★★★★
- **Tushare Pro** — 免费积分制，A股+宏观+期货 | ★★★★

### 宏观→加密传导机制
1. **利率→美元→BTC**（最强传导，2-4周延迟）
2. **M2流动性→BTC**（中期最强，6-12月领先）
3. 中国M2增速领先BTC约3-6个月

### BTC 5min模型推荐宏观因子
`DXY` | `VIX` | `US10Y` | `M2_YoY` | `Funding_Rate` | `Stablecoin_MCap_Change`

---

## 四、新闻与NLP

### 商业平台
- **RavenPack** — ESS事件情感，延迟<50ms，$25K-100K+/年 | ★★★★★
- **Bloomberg NLP** — 含Terminal | $20K-25K/年 | ★★★★

### 自建Pipeline（推荐！）
```
Scrapy(50+站点) → SimHash去重 → spaCy NER → FinBERT/GPT-4o-mini情感 → MongoDB+Redis
```
- GPT-4o-mini: ~$5-20/月(日均1000条)，输出 sentiment/confidence/affected_coins/event_type
- FinBERT(ProsusAI/finbert): 免费，金融领域专用

### 免费新闻API
CryptoPanic API | NewsAPI.org | Twitter/X API v2 | Reddit API | CryptoCompare

---

## 五、高频/Level 2数据

### 交易所WebSocket对比

| 维度 | Binance | OKX | Bybit |
|------|---------|-----|-------|
| 最快更新 | 100ms | 100ms | 100ms |
| 最大深度档 | 100 | 4000(TBT) | 500 |
| 稳定性 | ★★★★★ | ★★★★★ | ★★★★ |
| 流动性 | 最深 | 深 | 深(合约) |

### LOB重建方法
1. REST全量快照 + WS增量更新 + 每分钟REST校准
2. **Cryptofeed库**(bmoscon/cryptofeed) — 统一接口30+交易所，自动LOB重建
3. **Tardis.dev** — 历史tick级数据回测 | Pro $100/月

### Tick存储
- **QuestDB** — >100万行/秒写入，列式压缩10:1-100:1，免费开源（推荐）
- **kdb+/q** — 华尔街标准，$10K+/年
- **ClickHouse** — 大规模历史分析

推荐架构: `Exchange WS → Cryptofeed → QuestDB(热) → ClickHouse(冷/回测)`

---

## 六、BTC 5min系统升级优先级

### P0 立即实施（~$78/月）
1. Coinglass $49 → Funding Rate + OI + Liquidation
2. CryptoQuant $29 → Exchange Flow
3. DeFi Llama 免费 → DEX Volume + TVL
4. FRED 免费 → DXY + VIX + US10Y
5. Binance WS 免费 → L2 Order Book Imbalance

### P1 短期（+$78/月）
6. Santiment $49 → 链上+社交融合
7. Glassnode Pro $39 → 链上宏观
8. 自建Scrapy+FinBERT → 升级情绪分析

### 关键新因子
- **衍生品**: funding_rate, oi_change_5m, liq_volume_5m, long_short_ratio
- **微观结构**: obi(前5档), spread, trade_imbalance, vpin
- **链上**: exchange_net_flow, whale_txn_count, stablecoin_supply_change
