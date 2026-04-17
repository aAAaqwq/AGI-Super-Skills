# Polymarket S1猎杀Skill

**用途**: 定时扫描S1甜区机会 (75-85¢)，生成结构化报告

## 📋 扫描清单

| 品类 | 时间框架 | API Slug | 优先级 |
|------|----------|-----------|--------|
| BTC | 日盘 | bitcoin-above-on-march-{N} | P0 |
| ETH | 日盘 | ethereum-above-on-march-{N} | P0 |
| SOL | 日盘 | solana-above-on-march-{N} | P0 |
| Gold | 月盘 | gold-gc-above-end-of-march | P1 |
| BTC | 4h | btc-updown-4h-* | P2 |
| BTC | 1h | btc-updown-5m-* | P2 |

## ✅ S1条件

- **价格区间**: 75-85¢ (可放宽至75-90¢)
- **结算时间**: 24-72h (日盘最佳)
- **流动性**: volume > $10,000
- **Buffer**: 距离现价 >15%

## 🚫 已知限制

- 1h/4h/Weekly 为"涨/跌"二元盘 (价格0或1)，不适用S1区间策略
- 5min/15min盘需用browser扫描
- Search API格式: `?q=xxx`，不是 `?_s=xxx`

## 📊 报告模板

详见 `references/report-template.md`

---
**执行频率**: 每2小时扫描 (via cron)
**输出**: 推送Telegram报告 + 写入hunt-crypto-latest.json
