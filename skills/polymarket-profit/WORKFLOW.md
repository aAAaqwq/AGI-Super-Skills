# Polymarket 自动化工作流 v2.0

## 架构

```
小a (顶层设计) → 小quant (执行) → 结果汇报
```

## Cron 任务配置

### 1. 市场扫描 (每4小时)
- **执行者**: 小quant (agent: q)
- **任务**: 扫描目标市场，识别机会
- **推送**: 发现机会时推送到群

### 2. 策略分析 (每日 9:00)
- **执行者**: 小quant
- **任务**: 分析持仓，调整策略参数
- **推送**: 每日简报到群

### 3. 交易执行 (触发式)
- **执行者**: 小quant
- **条件**: 发现高确定性机会 (≥95%)
- **确认**: 推送后等待用户确认

## 数据流

```
browser-use → 扫描数据 → smart_scanner.py → 机会分析 → 推送
```

## 推送目标

- Telegram群: -1003890797239 (Daniel's super agents Center)
- 格式: 简洁的卡片式消息

## 文件

- `config/adaptive_strategy.json` - 策略参数
- `data/scan_results.jsonl` - 扫描历史
- `data/opportunities.json` - 当前机会
- `data/portfolio.json` - 持仓状态

## 指令模板

### 小quant执行指令

```
扫描市场：
1. 运行 smart_scanner.py
2. 分析结果
3. 如果有机会，推送到群

格式：
🎯 [市场名称]
📊 Yes: XX% | No: XX%
💰 机会: [策略名称]
📈 预期收益: XX%
✅ 建议操作: [buy_no/buy_yes] $X.XX
```
