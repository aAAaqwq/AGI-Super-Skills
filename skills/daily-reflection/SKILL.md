---
name: daily-reflection
description: Evening reflection — full P&L review and strategy adjustment at end of day
---

# 📝 每日反思 Skill

你是Quant。每晚23:15做全量P&L复盘。

## 准备工作
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
```

读取: SOUL.md, data/strategy-v4.md, memory/今天.md, data/trades-log.jsonl

## Step 1: 账户概览
```bash
# API获取余额+持仓
python3 skills/polymarket-api/scripts/poly_trade.py balance
python3 scripts/api_position_monitor.py
```
- 记录: Portfolio=$X, Cash=$X, 利用率X%
- 从Binance获取BTC/ETH/SOL实时价
- **日P&L**: 对比今早和现在的总资产
- **累计ROI**: 基准$56 (2/26初始资金)

## Step 2: 每笔交易复盘
从memory/今天.md找出所有今日交易，每笔详细分析:
- 市场名称 | 方向(Yes/No) | 买入价 | 现价/结算价 | 投入金额 | 盈亏$ | 盈亏%
- edge是否真实: 信息差来源是什么？事后看是否成立？
- 趋势分析是否正确: 入场时判断的趋势 vs 实际走势
- 如果亏损: 亏损原因是什么？可以避免吗？

## Step 3: 策略分层统计
按策略层级分组:
- S1甜区: 笔数/胜率/总P&L/平均回报
- S2精选: 笔数/胜率/总P&L
- S-Elon: 推文盘表现
- S3套利: 是否发现机会
- **哪个策略表现最好？哪个最差？为什么？**

## Step 4: 风控审计
- 有没有违反铁律？(买>85¢? BTC>40%? 体育/地缘? 逆势买入?)
- 止损是否执行？有没有该止损没止的？
- 仓位集中度是否合理？

## Step 5: 市场环境回顾
- 今日市场整体情绪(恐慌/贪婪/中性)
- 有无重大事件影响市场
- 哪些品类表现好/差

## Step 6: 明日调整计划
- 具体的策略参数调整(价格区间/仓位比例/品类偏好)
- 明日重点关注的市场/事件
- 需要改进的执行细节

## 输出
1. 写入 memory/今天.md 末尾(完整反思内容)
2. 推送到DailyNews群:
```bash
python3 ~/clawd/scripts/newsbot_send.py "报告内容"
```
3. 如果发现重要教训，更新SOUL.md血泪教训或MEMORY.md

## 变更记录
- v1.0 (2026-03-15): 从cron prompt迁移为skill
