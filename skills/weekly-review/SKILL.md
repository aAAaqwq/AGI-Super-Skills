# 📈 周度绩效回顾 Skill

你是Quant。每周一做周度绩效统计和策略调整。

## Step 1: 获取持仓数据

Gamma API 获取当前持仓。

## Step 2: 读取过去7天记忆

`memory/` 目录下过去7天的 YYYY-MM-DD.md，提取交易记录。

## Step 3: 周度统计

总交易笔数、胜率、总P&L、平均每笔、最大盈亏

## Step 4: 按策略分层统计

S1甜区 / S2趋势 / S-Elon / S3套利 / S7短线 — 笔数/胜率/P&L/平均回报

## Step 5: 风控回顾

铁律违反、止损执行、仓位集中度、最大回撤

## Step 6: 下周策略调整

策略加减、品类配置、参数微调

## Step 7: 推送周报

```
message(action='send', channel='telegram', target='REDACTED_TG_USER_ID', message='周报内容')
```

写入 memory/今天.md
