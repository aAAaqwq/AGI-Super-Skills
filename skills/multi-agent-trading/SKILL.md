# SKILL.md — Multi-Agent Trading Framework (蒸馏自 TauricResearch/TradingAgents)

> 版本: 1.0 | 来源: https://github.com/TauricResearch/TradingAgents | Apache-2.0 License
> 论文: arXiv:2412.20138 | AAAI 2025 MARW Workshop
> 适配: CQO Simons · 用于多Agent协作交易决策

## 触发词

`multi-agent trading`, `交易团队`, `analyst team`, `trading debate`, `bull bear debate`, `协作交易`, `agent trading framework`

## 核心理念

**模拟真实交易公司的协作动态** — 不同角色的 LLM Agent 通过结构化通信 + 辩论机制, 形成比单Agent更优的交易决策。

> 实验结果: 年化收益最高 30.5%, Sharpe Ratio 和最大回撤均优于基线 (Buy&Hold, MACD, KDJ, RSI, ZMR, SMA)

## 架构: 五层协作

```
┌─────────────────────────────────────────────┐
│           I. ANALYST TEAM (并行)             │
│  Fundamental │ Sentiment │ News │ Technical  │
└────────────────────┬────────────────────────┘
                     │ 结构化报告
                     ▼
┌─────────────────────────────────────────────┐
│          II. RESEARCH TEAM (辩论)            │
│         Bull Researcher vs Bear Researcher   │
└────────────────────┬────────────────────────┘
                     │ 辩论纪要
                     ▼
┌─────────────────────────────────────────────┐
│              III. TRADER AGENT               │
│    综合分析师+研究员观点 → 交易信号+理由      │
└────────────────────┬────────────────────────┘
                     │ 交易计划
                     ▼
┌─────────────────────────────────────────────┐
│          IV. RISK MANAGEMENT TEAM            │
│     多角度风险评估 → 风险调整建议             │
└────────────────────┬────────────────────────┘
                     │ 审批
                     ▼
┌─────────────────────────────────────────────┐
│             V. FUND MANAGER                  │
│        最终审批 + 执行                        │
└─────────────────────────────────────────────┘
```

## 角色 specialization

### Analyst Team (4个并行Agent)

| 角色 | 数据源 | 输出 |
|------|--------|------|
| **Fundamental Analyst** | 财报, 估值, 盈利, 机构持仓 | 估值报告, 是否被高/低估 |
| **Sentiment Analyst** | 社交媒体 (Reddit/X), Polymarket | 情绪得分, 看多/看空比例 |
| **News Analyst** | 新闻, 宏观指标 | 事件影响评估, 方向预判 |
| **Technical Analyst** | K线, 指标 (RSI/MACD/布林带) | 技术信号, 支撑/阻力位 |

### Research Team (辩论机制)

```
Bull Researcher: 找正面信号, 强调机会
Bear Researcher: 找负面信号, 强调风险
→ 通过多轮辩论形成平衡观点
→ 输出: 看多/看空置信度 + 关键论据
```

### Trader Agent
- 接收: 分析师报告 + 研究员辩论纪要 + 历史数据
- 输出: buy/sell/hold + 仓位比例 + 详细理由
- 考虑: 交易成本, 滑点, 流动性

### Risk Management Team
- 评估: 波动率, 流动性, 集中度, 相关性
- 输出: 风险调整建议 (减仓/加仓/止损位)
- 约束: 单笔风险上限, 总暴露上限

### Fund Manager
- 综合所有信息 + 风险评估
- 最终决策: approve / modify / reject

## 通信协议

### 关键创新: 结构化输出 > 自然语言

```
Analyst → Structured Report (JSON/表格)    ← 信息密度高, 无损
Researcher → Natural Language Debate        ← 辩论用自然语言, 促进深度推理
Trader → Decision Signal + Rationale        ← 结构化
Risk Manager → Natural Language Deliberation ← 多角度讨论
Fund Manager → Final Approval               ← 结构化
```

### 模型路由策略

| 任务 | 模型要求 | 原因 |
|------|---------|------|
| 数据获取/格式化 | 快速模型 (GPT-4o-mini) | 简单任务, 省成本 |
| 深度分析/辩论 | 深度模型 (Claude/GPT-4) | 需要强推理 |
| 最终决策 | 最强模型 | 单次调用, 高价值 |

> 全程无需 GPU, 纯 API 调用。

## CQO 集成方案

### 方案 A: 完整多Agent (推荐用于重大决策)

```python
# 用 OpenClaw sessions_spawn 实现
# Step 1: 并行 spawn 4个 Analyst subagents
analysts = ["fundamental", "sentiment", "news", "technical"]
reports = {}
for role in analysts:
    sessions_spawn(task=f"作为{role}分析师, 分析 {symbol}", ...)

# Step 2: Bull/Bear 辩论 (可用 steer 在同一session)
# Step 3: Trader 综合
# Step 4: Risk 评估
# Step 5: Fund Manager 审批
```

### 方案 B: 轻量版 (日常快速决策)

单Agent + 多轮prompt, 模拟5层流程:
```
Round 1: "同时作为4个分析师, 给出报告"
Round 2: "作为Bull研究员, 反驳/支持以上结论" → "作为Bear研究员, 反驳"
Round 3: "作为Trader, 综合以上, 给出交易信号"
Round 4: "作为风控, 评估风险"
Round 5: "作为Fund Manager, 最终决策"
```

### 适用场景

| 场景 | 推荐方案 |
|------|---------|
| BTC/ETH 大额开仓 (>5% portfolio) | A: 完整多Agent |
| Polymarket 甜区交易 | B: 轻量版 |
| 每日持仓复盘 | B: 轻量版 |
| 新策略上线决策 | A: 完整多Agent |

## 回测方法论 (论文验证)

- **数据**: 多资产 (股票), 多模态 (价格+新闻+情绪+内幕+财报+技术指标)
- **时间**: 2024.01-03 训练, 2024.06-11 测试
- **无未来信息泄露**: Agent 只能看到当前及之前数据
- **基线对比**: Buy&Hold, MACD, KDJ+RSI, ZMR均值回归, SMA均线
- **指标**: 累计收益, Sharpe Ratio, 最大回撤
- **结果**: 在 AAPL/GOOGL/AMZN 上全面优于所有基线

## 关键洞察 (Simons 评价)

1. **辩论机制是核心创新** — Bull vs Bear 强制平衡分析, 减少 confirmation bias
2. **角色specialization** — 比单Agent全知全能更接近真实交易团队
3. **模型路由** — 简单任务用便宜模型, 关键决策用贵模型, 成本可控
4. **可解释性** — 每步决策有自然语言理由, 可审计
5. **⚠️ 局限**: 
   - 回测期仅6个月, 样本偏小
   - 未扣交易成本/滑点
   - 依赖 LLM 质量, 模型切换可能影响策略稳定性
   - 仅测试美股, 加密/预测市场未验证

## Prompt 模板 (核心)

### Analyst Prompt
```
You are a {role} analyst for {symbol}.
Current date: {date}
Available data: {data_summary}

Provide a structured analysis:
1. Key metrics and signals
2. Direction: Bullish/Bearish/Neutral (confidence: X%)
3. Top 3 factors driving your view
4. Data gaps or concerns

Output as structured report.
```

### Debate Prompt
```
You are a {bull/bear} researcher.
Analyst reports: {reports}
Counter-argument: {opponent_view}

Argue your position. Address the opponent's points.
Focus on evidence, not rhetoric.
```

---
*蒸馏日期: 2026-05-01 | 原论文 arXiv:2412.20138, Apache-2.0 License*
