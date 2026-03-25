# Quant Skills — Polymarket量化交易

Daniel Li的Polymarket量化交易AI（Quant/量子）使用的全部skill。

## Skills (9个)

| Skill | 用途 | Cron频率 |
|-------|------|----------|
| 🔧 polymarket-api | 底层API层：CLOB交易/余额/持仓/Relayer | 非cron |
| 📰 news-predictor | 新闻预测→风险等级(DANGER/CAUTION/NEUTRAL) | 每1h |
| 🔍 crypto-hunt | S1甜区扫描+趋势+入场时机 | 每1h |
| ⚡ hunt-report | 猎杀报告（不交易） | 每4h |
| 📊 position-monitor | 止盈止损+峰值追踪+Claim检测 | 每1h |
| 🐦 elon-tweets | Elon推文盘分析 | 21-03点每1h |
| 📊 daily-portfolio | 持仓日报 | 09:30 |
| 📝 daily-reflection | P&L复盘+策略评估 | 23:15 |
| 📈 weekly-review | 周度绩效统计 | 周一10:00 |

## Scripts (5个)

| 脚本 | 用途 |
|------|------|
| trend_analysis.sh | BTC/ETH/SOL/GOLD 4h K线+24h涨跌 |
| scan_markets.sh | Polymarket Above+涨跌日盘扫描 |
| entry_timing.sh | RSI/MA20/赔率趋势→ENTRY_NOW/WAIT/SKIP |
| api_position_monitor.py | 仓位止盈止损+峰值追踪 |
| elon_analyze.py | Elon推文盘独立分析 |

## 依赖
- Polymarket Gamma API + CLOB API
- Binance API (data-api.binance.vision)
- OpenClaw workspace at `~/.openclaw/workspace-quant`
