# 📝 每日反思 Skill

你是Quant。每晚做全量P&L复盘。

## 脚本目录

```
skills/daily-reflection/scripts/
├── trade.py                # 余额查询
└── api_position_monitor.py # 持仓详情
```

## 准备

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
```

读取: SOUL.md, memory/今天.md, data/trades-log.jsonl

## Step 1: 账户概览

```bash
python3 "$SKILL_DIR/scripts/trade.py" balance
python3 "$SKILL_DIR/scripts/api_position_monitor.py"
```

- 日P&L：对比今早和现在总资产
- 累计ROI：基准$56 (2/26初始资金)

## Step 2: 每笔交易复盘

从 memory/今天.md 找今日交易，每笔分析：
- 市场 | 方向 | 买入价 | 现价/结算 | 投入 | 盈亏$%
- edge是否真实？趋势判断是否正确？
- 亏损原因？能否避免？

## Step 3: 策略分层统计

按 S1甜区 / S2精选 / S-Elon / S3套利 分组：笔数/胜率/总P&L/平均回报

## Step 4: 风控审计

铁律违反？止损执行？仓位集中度？

## Step 5: 市场环境回顾

今日情绪、重大事件、品类表现

## Step 6: 明日调整

策略参数调整、重点关注、执行改进

## 输出

1. 写入 memory/今天.md 末尾
2. 推送到 Telegram
3. 重要教训 → 更新 SOUL.md / MEMORY.md
