---
name: position-monitor
description: Hourly position monitor — execute take-profit/stop-loss and track peak gains
---

# 📊 仓位监控+止盈止损 Skill v3.0 (API-based)

你是Quant。每小时检查持仓，执行止盈止损，追踪盈利峰值。

## 执行方式

**优先使用API脚本**（零token消耗、速度快）：
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
python3 ${WORKSPACE}/scripts/api_position_monitor.py
```

实时交易模式（实际执行卖出）：
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
python3 ${WORKSPACE}/scripts/api_position_monitor.py --live
```

**Browser为fallback**（API失败时）：参照下方Step 3。

## 数据源

| 数据 | API来源 | 说明 |
|------|---------|------|
| 持仓 | CLOB `get_trades()` 重建 | 从交易历史聚合净仓位+当前价格 |
| 现金余额 | CLOB `get_balance_allowance()` | USDC余额 |
| 现价 | CLOB `get_price(token_id)` | 实时报价 |
| BTC/ETH价格 | Binance API | 趋势分析 |
| 可Claim仓位 | CLOB trades (price=0, net>0) | 已结算待认领 |

⚠️ **data-api `/positions` 不可靠**（经常返回空），用CLOB trades重建替代。

## 止盈止损规则 v5.0（按优先级执行）

### 止损（先检查）
| # | 条件 | 动作 |
|---|------|------|
| SL1 | 亏 > 40% | **全部止损** |
| SL2 | 亏 > 25% | **减仓40%** |
| SL3 | 亏 > 15% 且 4h连跌2根+buffer<3% | **止损一半** |

### 止盈（再检查）
| # | 条件 | 动作 |
|---|------|------|
| TP1 | 现价 ≥ 99¢ 且 结算 > 4h | **全卖**（1¢不值等）|
| TP2 | 盈利 ≥ 50% | **全卖** |
| TP3 | 盈利 ≥ 30% 且 现价 ≥ 95¢ | **全卖**（上升空间<5¢）|
| TP4 | 盈利 ≥ 25% | **卖50%** |
| TP4b | 盈利 ≥ 15% | **卖60%** |
| TP5 | 盈利峰值回撤 ≥ 10pp（且峰值≥10%）| **卖50%** |
| TP6 | 利润腰斩相对值（且峰值≥10%）| **全卖** |

### TP5/TP6 说明
- 峰值+25%，现在+15% → 回撤10pp → **TP5卖半**
- 峰值+20%，现在+10% → 回撤10pp且=50%峰值 → **TP6全卖**
- 峰值+12%，现在+2% → 回撤10pp → **TP5卖半**
- 峰值+8%，现在+5% → 回撤3pp，峰值<10% → **不触发**

## Browser Fallback（API失败时）

Step 3-7: 与v2.0相同，用browser打开portfolio、snapshot、执行操作。

## 变更记录
- v3.0 (2026-03-24): API化重构。CLOB trades重建持仓替代data-api/browser，支持`--live`执行卖出
- v2.0 (2026-03-17): Daniel指令重设止盈止损。新增TP4/TP5/TP6回撤止盈，profit-peaks.json峰值追踪
- v1.0 (2026-03-15): 从cron prompt迁移为skill
