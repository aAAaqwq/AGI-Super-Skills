# Polymarket 5min BTC 数据源分析

> 2026-05-27 调研结论

## 核心结论

Polymarket 5min BTC 方向盘口使用 **Chainlink Data Streams** 的 BTC/USD 价格结算，不是单一交易所价格。

Polymarket 官方明确标注：
> *"This market is about the price according to Chainlink data stream BTC/USD, not according to other sources or spot markets"*

## Chainlink Data Streams 聚合方式

1. **数据源**: 3+ 家独立的加密价格数据聚合商/市场数据供应商
2. **原始数据**: 多个 CEX（中心化交易所）订单簿数据聚合
3. **共识机制**: DON 节点从多个数据提供商获取价格 → 中位数共识（median consensus）
4. **输出字段**:
   - `benchmarkPrice` (中位价，18位小数)
   - `bid` (模拟买入冲击价，X%流动性深度)
   - `ask` (模拟卖出冲击价)
   - Schema: V3 (Crypto Advanced)

## 与 Binance BTCUSDT 价差（2026-05-27 实测）

```
交易所                价格          vs均值
Coinbase BTC-USD    $75,088.99    -$57
Kraken XBTUSD       $75,104.10    -$42
Binance BTCUSD      $75,105.19    -$40
CoinGecko (agg)     $75,123.00    -$23
OKX BTC-USDT        $75,218.60    +$73
Binance BTCUSDT     $75,233.81    +$88  ← 引擎数据源

最大价差: $145 (0.19%)
```

## 对预测引擎的影响

### 场景1: 价差导致结算方向不同
如果5min K线收盘时价格变动恰好落在交易所价差范围内（±$50-150），可能出现：
- Binance: 从$75,100涨到$75,130 → bull (+$30)
- Chainlink中位数: 从$75,050涨到$75,070 → bull (+$20) ✅ 方向一致
- 但如果 Chainlink中位数仅涨到$75,049 → bear (-$1) ❌ 方向相反

### 场景2: 价差放大误差
引擎用Binance数据预测方向，但Polymarket用Chainlink结算。
当价格波动在价差范围内时，引擎预测的"正确性"取决于Binance而非Chainlink。

### 风险等级
- **低风险**: 价格波动 > $200 (远超价差，方向必然一致)
- **中风险**: 价格波动 $50-200 (大概率一致，但价差可能吃掉部分)
- **高风险**: 价格波动 < $50 (方向可能因价差翻转)

## 建议

1. **短期**: 在vol<50%的K线上标注"低波动-结算风险"，降低置信度
2. **中期**: 接入Chainlink Data Streams API获取实时中位价，与Binance价格做差异监控
3. **长期**: 引擎改用Chainlink价格作为基准数据源

## 参考链接

- Chainlink Data Feeds 数据源说明: https://docs.chain.link/data-feeds/data-sources
- Chainlink Data Streams 架构: https://docs.chain.link/data-streams/architecture
- V3 Report Schema (Crypto): https://docs.chain.link/data-streams/reference/report-schema-v3
- Chainlink 流动性加权价格: https://docs.chain.link/data-streams/concepts/liquidity-weighted-prices
