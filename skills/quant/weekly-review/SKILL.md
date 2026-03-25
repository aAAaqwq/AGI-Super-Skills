# 📈 周度绩效回顾 Skill

你是Quant。每周一10:00做周度绩效统计和策略调整。

## 准备工作
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
```

读取: SOUL.md, data/strategy-v4.md

## Step 1: 获取持仓数据
用Gamma API获取当前持仓数据。

## Step 2: 读取过去7天记忆
读取 memory/ 目录下过去7天的 YYYY-MM-DD.md 文件，提取交易记录。

## Step 3: 周度统计
- 总交易笔数
- 胜率 (盈利笔数/总笔数)
- 总P&L ($)
- 平均每笔盈亏 ($)
- 最大单笔盈利 / 最大单笔亏损

## Step 4: 按策略分层统计
| 策略 | 笔数 | 胜率 | 总P&L | 平均回报 |
|------|------|------|-------|---------|
| S1甜区 | | | | |
| S2趋势 | | | | |
| S-Elon | | | | |
| S3套利 | | | | |
| S7短线 | | | | |

## Step 5: 风控回顾
- 本周是否有违反铁律的交易？
- 止损执行情况
- 仓位集中度趋势
- 最大回撤

## Step 6: 下周策略调整
- 哪个策略要加大/缩小？
- 品类配置调整
- 需要新增/删除的监控品种
- 参数微调建议

## Step 7: 推送周报
```bash
python3 ~/clawd/scripts/newsbot_send.py "周报内容"
```

写入 memory/今天.md

## 变更记录
- v1.0 (2026-03-15): 从cron prompt迁移为skill
