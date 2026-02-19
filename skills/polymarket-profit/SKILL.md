# Polymarket 量化投资系统

真实交易系统，$3 本金在 Polymarket 预测市场上执行量化策略。

## 概述

- **模式**: 真实交易（非模拟盘）
- **本金**: $3 USDC (Polygon)
- **策略**: 高确定性套利 + CME 套利 + 事件驱动
- **推送**: DailyNews 群 (@fkkanfnnfbot → -1003824568687)
- **负责 Agent**: quant（量化投资专员）
- **协作**: finance（资金核算）、research（情报）、news（新闻）

## 核心策略

### 1. 高确定性 No (60% 仓位 ~$1.80)
- 买入短期内极不可能发生事件的 No
- 条件: No ≥ 85%, 剩余 ≤ 60 天
- 预期: 15-25% 年化

### 2. CME 套利 (20% 仓位 ~$0.60)
- Polymarket vs CME FedWatch 利率预期价差
- 条件: 价差 > 5%
- 预期: 低风险稳定

### 3. 事件驱动 (20% 仓位 ~$0.60)
- 基于新闻情报的信息优势交易
- 需要 research/news 支持
- 中风险高回报

## 风控

| 规则 | 值 |
|------|------|
| 单笔上限 | $1 |
| 最少分散 | 3 个市场 |
| 止损线 | 赔率反向 15% |
| 总本金 | $3 |

## 文件结构

```
skills/polymarket-profit/
├── SKILL.md              # 本文件
├── config/
│   ├── markets.json      # 关注市场列表
│   └── strategies.json   # 策略配置
├── scripts/
│   ├── fetcher.py        # Polymarket 数据抓取
│   ├── analyzer.py       # 机会分析引擎
│   └── trader.py         # 真实交易执行模块
├── data/
│   ├── odds/             # 赔率历史快照 (JSONL)
│   ├── portfolio.json    # 当前持仓
│   ├── trade_log.json    # 交易日志
│   └── reports/          # 投资报告
└── templates/
    └── daily_report.md   # 推送模板
```

## 使用

```bash
# 查看持仓
python3 scripts/trader.py status

# 健康检查
python3 scripts/trader.py health

# 生成交易指令
python3 scripts/trader.py instruction --market <slug> --outcome No --amount 0.6 --price 0.85
```

## 交易流程

1. quant agent 每日分析赔率快照 → 生成交易建议
2. 推送到 DailyNews 群
3. 用户确认 → 执行交易（网页手动 或 API 自动）
4. 记录到 trade_log.json + portfolio.json
5. finance agent 每周核算盈亏

## 前置条件

- [ ] Polymarket 账户（钱包登录）
- [ ] $3 USDC 在 Polygon 网络
- [ ] 少量 MATIC (gas)
- [ ] (可选) Polymarket API Key
- [ ] (可选) 钱包私钥（全自动模式）
