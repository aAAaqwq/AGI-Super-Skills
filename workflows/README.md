# Workflows — 团队工作流库

> **精明的工作流 = 明确的触发条件 + 标准化的执行步骤 + 可量化的输出**

## 结构

```
workflows/
├── shared/          ← 跨 Agent 通用流程
│   ├── daily-standup.md
│   ├── weekly-review.md
│   ├── crisis-escalation.md
│   └── cross-agent-handoff.md
├── ceo/             ← CEO 工作流
├── cco/             ← 首席内容官
├── cdo/             ← 首席数据官
├── cfco/            ← 首席财务官
├── clo/             ← 首席法务官
├── cmo/             ← 首席营销官
├── coo/             ← 首席运营官
├── cpo/             ← 首席产品官
├── cqo/             ← 首席量化官
├── cro/             ← 首席研究官
├── cso/             ← 首席销售官
└── pe/              ← CTO-Dev
```

## 工作流规范

每个工作流遵循统一格式：

```markdown
# 工作流名称

## 元信息
- **触发条件**: 什么时候执行
- **执行频率**: 每天/每周/按需
- **预计耗时**: 分钟
- **负责 Agent**: 主执行人
- **协作 Agent**: 需要配合的人

## 输入
执行前需要准备什么

## 执行步骤
1. 步骤一（具体动作，不是笼统描述）
2. 步骤二
...

## 输出
执行后产出什么（文件/消息/数据）

## 质量门禁
什么标准算完成

## 异常处理
出问题怎么办
```

## 索引

| 分类 | 工作流 | 频率 | 负责 |
|------|--------|------|------|
| 🔄 通用 | [每日站会](shared/daily-standup.md) | 每天 08:00 | CEO |
| 🔄 通用 | [周度复盘](shared/weekly-review.md) | 每周日 20:00 | CEO |
| 🔄 通用 | [危机升级](shared/crisis-escalation.md) | 按需 | 任意 → CEO |
| 🔄 通用 | [跨 Agent 交接](shared/cross-agent-handoff.md) | 按需 | 发起方 |
| 📊 CCO | [内容发布管线](cco/content-pipeline.md) | 每天 | CCO |
| 📊 CCO | [爆款复盘](cco/viral-debrief.md) | 每周 | CCO |
| 📊 CCO | [内容日历规划](cco/content-calendar.md) | 每周 | CCO |
| 📊 CDO | [数据采集巡检](cdo/data-collection-audit.md) | 每天 | CDO |
| 📊 CDO | [API 健康检查](cdo/api-health-check.md) | 每天 | CDO |
| 📊 CFO | [每日盈亏](cfo/daily-pnl.md) | 每天 | CFO |
| 📊 CFO | [成本优化扫描](cfo/cost-optimization.md) | 每周 | CFO |
| 📊 CQO | [市场晨报](cqo/market-morning-brief.md) | 每天 08:00 | CQO |
| 📊 CQO | [策略回测](cqo/strategy-backtest.md) | 每周 | CQO |
| 📊 CMO | [SEO 健康检查](cmo/seo-health-check.md) | 每周 | CMO |
| 📊 CMO | [竞品监控](cmo/competitor-monitor.md) | 每周 | CMO |
| 📊 CPO | [需求优先级排序](cpo/priority-sorting.md) | 每周 | CPO |
| 📊 CPO | [功能验收](cpo/feature-acceptance.md) | 按需 | CPO |
| 📊 COO | [系统健康巡检](coo/system-health-check.md) | 每天 | COO |
| 📊 COO | [故障响应](coo/incident-response.md) | 按需 | COO |
| 📊 CRO | [行业情报扫描](cro/industry-scan.md) | 每天 | CRO |
| 📊 CRO | [深度研究管线](cro/deep-research-pipeline.md) | 每周 | CRO |
| 📊 CSO | [获客漏斗巡检](cso/lead-funnel-check.md) | 每天 | CSO |
| 📊 CSO | [触达节奏优化](cso/outreach-cadence.md) | 每周 | CSO |
| 📊 CLO | [合规巡检](clo/compliance-audit.md) | 每周 | CLO |
| 📊 CLO | [合同审查](clo/contract-review.md) | 按需 | CLO |
| 📊 PE | [代码审查](pe/code-review.md) | 每天提交后 | PE |
| 📊 PE | [技术债审计](pe/tech-debt-audit.md) | 每周 | PE |
| 📊 PE | [部署流水线](pe/deploy-pipeline.md) | 按需 | PE |
| 📊 PE | [性能剖析](pe/performance-profiling.md) | 按需 | PE |

---

*基于 AGI Super Team 团队模板 · [OpenClaw](https://github.com/openclaw/openclaw)*
