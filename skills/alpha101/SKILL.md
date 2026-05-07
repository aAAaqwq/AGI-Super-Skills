---
name: alpha101
description: |
  WorldQuant 101 Formulaic Alphas — 因子计算、IC测试、回测一体化工具包。
  基于Kakushadze (2015) 论文，提供101个价量/波动率/相关性因子的Python/Pandas实现。
  Use when: "alpha101", "101因子", "formulaic alphas", "因子回测", "因子IC", "因子筛选",
  "WorldQuant因子", "价量因子", "alpha因子库".
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(python:*)
version: 1.0.0
author: Simons (CQO)
---

# Alpha101 — WorldQuant 101 Formulaic Alphas

## 概述

Zura Kakushadze 论文《101 Formulaic Alphas》(arXiv:1601.00991) 的完整Python实现。
101个真实量化交易alpha因子，公式即代码。

### 论文关键数据
- 平均持仓期: 0.6-6.4天
- 平均两两相关性: 15.9%
- 收益与波动率强相关: R ~ σ^0.76

## 文件结构

```
skills/alpha101/
├── SKILL.md              ← 本文件
├── scripts/
│   ├── alpha101.py       ← 101个因子函数 + 基础函数库
│   ├── compute_ic.py     ← 因子IC/IR计算
│   └── backtest_alpha.py ← 单因子回测
└── references/
    └── paper_notes.md    ← 论文笔记与函数定义
```

## 使用方式

### 1. 因子计算

```python
from scripts.alpha101 import compute_alphas, alpha101

# 输入: date x ticker DataFrame
data = {
    'open': df_open, 'close': df_close, 'high': df_high, 'low': df_low,
    'volume': df_vol, 'vwap': df_vwap, 'returns': df_returns
}

# 计算所有可用因子
alphas = compute_alphas(data)  # dict of alpha_name -> DataFrame

# 单独计算
from scripts.alpha101 import alpha101
a101 = alpha101(df_open, df_close, df_high, df_low)
```

### 2. 因子IC测试

```bash
python scripts/compute_ic.py --data <path> --output results/
```

### 3. 单因子回测

```bash
python scripts/backtest_alpha.py --alpha 101 --data <path>
```

## 因子分类

| 类别 | 因子 | 输入 |
|------|------|------|
| 纯价量 | #1-#47, #49-#55, #60, #61, #71-#74, #84, #88, #101 | OHLCV + VWAP |
| 行业中性化 | #48, #56, #58-#59, #63, #67, #69-#70, #76, #79-#82, #87, #89-#91, #93, #97, #100 | + 行业分类 |
| 复杂参数 | #57-#99 | 非整数窗口, 混合权重 |

## 基础函数速查

```
rank(x)              截面排名 [0,1]
delay(x,d)           d天前的值
delta(x,d)           当期 - d天前
correlation(x,y,d)   d天滚动相关
scale(x,a=1)         缩放使sum(abs(x))=a
decay_linear(x,d)    线性衰减加权均值
ts_min/ts_max(x,d)   滚动最小/最大
ts_rank(x,d)         时间序列排名
ts_sum/ts_std(x,d)   滚动求和/标准差
adv{d}               d天平均成交额
IndNeutralize(x,ind) 行业中性化
```

## 回测注意事项

1. **交易成本**: 论文因子扣除cost后Sharpe才是真Sharpe
2. **过拟合**: 101个因子中部分可能已衰减，需样本外验证
3. **市场适配**: 
   - A股: T+1限制，持仓期需调整
   - 加密: 24/7，日频→小时频需改窗口参数
   - Polymarket: 流动性低，部分因子不适用
4. **行业因子**: 需要行业分类映射，加密市场可用板块替代

## 决策框架

```
因子计算 → IC/IR筛选(>0.03) → 样本外验证 → 组合构建(低相关等权) → 回测扣费 → 实盘
```
