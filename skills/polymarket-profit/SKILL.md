# Polymarket 高盈利预测方案

每日分析 Polymarket 预测市场，推送高盈利机会到 DailyNews 群。

## 概述

- **目标**: 用 $3 本金在 Polymarket 上最大化盈利
- **策略**: 低风险套利 + 信息优势预测
- **推送**: 每日 20:00 CST 推送到 Telegram DailyNews 群
- **交易所**: OKX（USDT → USDC → Polygon）

## 核心策略

### 低风险策略（本金 < $5）
1. **Holding Rewards 套利** - 4% 年化，同时买 Yes/No
2. **Fed 利率市场套利** - 与 CME FedWatch 对比，>5% 差价时下注
3. **高确定性事件 No** - 如 "Claude 5 by X date" No（低风险稳定）

### 中风险策略（本金 $10-50）
1. **体育赛事赔率波动** - 冬奥会/世界杯等
2. **事件预测（信息优势）** - 政府关门、产品发布等

### 风险控制
- 本金 $3 **只用低风险策略**
- 每次最大下注 **$1**
- 分散 **3 个市场**

## 数据源

| 数据源 | 用途 | 方式 |
|--------|------|------|
| Polymarket API | 实时赔率、交易量 | CLOB API / Gamma API |
| CME FedWatch | 利率预期对比 | web_fetch |
| 官方公告 | 产品发布、政策 | web_fetch |
| 新闻源 | 事件跟踪 | web_fetch |

## 使用方法

### 手动运行
```bash
cd skills/polymarket-profit
python3 scripts/daily_analyzer.py
```

### Cron 自动推送
每日 20:00 CST 自动运行并推送到 DailyNews 群。

## 文件结构

```
skills/polymarket-profit/
├── SKILL.md              # 本文件
├── config/
│   ├── markets.json      # 关注市场列表
│   └── strategies.json   # 策略配置
├── scripts/
│   ├── daily_analyzer.py # 每日分析主脚本
│   ├── fetcher.py        # Polymarket 数据抓取
│   └── analyzer.py       # 机会分析引擎
├── data/
│   ├── odds/             # 赔率历史记录
│   └── predictions/      # 预测记录与复盘
└── templates/
    └── daily_report.md   # 推送模板
```

## 推送目标

- **Telegram Bot**: @fkkanfnnfbot (NewsRobot)
- **群组**: DailyNews (`-1003824568687`)
- **格式**: HTML（支持加粗、链接）
