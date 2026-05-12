# SKILL.md — LLM Stock Analyzer (蒸馏自 ZhuLinsen/daily_stock_analysis)

> 版本: 1.0 | 来源: https://github.com/ZhuLinsen/daily_stock_analysis | MIT License
> 适配: CQO Simons · 用于 A股/港股/美股 LLM 驱动分析

## 触发词

`stock analysis`, `个股分析`, `A股分析`, `港股分析`, `美股分析`, `daily analysis`, `决策仪表盘`

## 核心架构

```
数据采集 → 多维分析 → AI决策仪表盘 → 多渠道推送
```

### 1. 数据采集层

| 数据类型 | 来源 (优先级) | 用途 |
|----------|--------------|------|
| 实时行情 | AkShare → Tushare → Pytdx → Baostock | OHLCV + 技术指标 |
| 美股行情 | YFinance | OHLCV (复权一致) |
| 新闻搜索 | Tavily → SerpAPI → Bocha → Brave | 舆情情报 |
| 社交情绪 | Stock Sentiment API (Reddit/X) | 美股情绪 |
| 基本面 | AkShare (估值/成长/盈利/机构/资金流/龙虎榜) | 结构化聚合 |
| 筹码分布 | AkShare (可选, 接口不稳定) | A股筹码 |

**关键设计**: fail-open 降级 — 任一数据源失败不阻塞主流程。

### 2. 分析维度

| 维度 | 输出 |
|------|------|
| **技术面** | MA5/10/20 多头排列, 盘中实时MA, 趋势判断 |
| **筹码分布** | 成本分布, 获利盘比例 (A股) |
| **舆情情报** | 新闻时效窗口 (默认3天), 情绪倾向 |
| **实时行情** | 涨跌幅, 振幅, 成交量变化 |
| **基本面** | 估值/成长/盈利/机构持仓/资金流/龙虎榜/板块涨跌 |

### 3. AI 决策仪表盘输出格式

```markdown
## 📊 [股票代码] 决策仪表盘

### 一句话核心结论
[做多/做空/观望] + 置信度

### 精确点位
- 买入价: ¥XX.XX
- 止损价: ¥XX.XX
- 目标价: ¥XX.XX

### 操作检查清单
| 条件 | 状态 |
|------|------|
| MA多头排列 | ✅ 满足 / ⚠️ 注意 / ❌ 不满足 |
| 乖离率 < 5% | ... |
| 成交量放大 | ... |
| 新闻无重大利空 | ... |
```

### 4. 内置交易纪律

| 规则 | 实现 |
|------|------|
| **严禁追高** | 乖离率 > 5% (可配) → 自动提示风险; 强势趋势股放宽 |
| **趋势确认** | MA5 > MA10 > MA20 多头排列 |
| **点位精确** | 买入/止损/目标 三价齐出 |
| **新闻时效** | 默认3天, 超时新闻降权 |

### 5. 策略系统

**A股三段式复盘策略**:
1. 市场概览 (大盘指数 + 板块涨跌)
2. 个股技术面扫描
3. 综合决策 + 操作计划

**美股 Regime Strategy**:
- risk-on / neutral / risk-off 三档切换
- 基于宏观指标 + 技术信号

**Agent 问股** (11种内置策略):
- 均线金叉, 缠论, 波浪理论, 多头趋势等
- 多轮对话, 流式进度, 会话持久化

### 6. 多 Agent 架构 (实验性)

设置 `AGENT_ARCH=multi` 启用:
```
Technical Agent → Intel Agent → Risk Agent → Strategy Agent → Decision Agent
```
- 超时/解析失败时降级到单Agent输出最小仪表盘
- `AGENT_ORCHESTRATOR_MODE`: quick / standard / full / strategy

### 7. 回测验证

- 自动评估历史分析准确率
- 指标: 方向胜率, 止盈命中率, 止损命中率
- 关键: 确认信号发出时点 vs 实际可执行价格

## CQO 集成指南

### 适用场景
- Polymarket 7币种 + A股/美股的每日分析增强
- 替代手工看盘, 自动生成决策仪表盘

### API 接入 (推荐路径)
```python
# LiteLLM 统一调用
from litellm import completion

response = completion(
    model="deepseek/deepseek-chat",
    messages=[{"role": "system", "content": ANALYSIS_PROMPT}],
    temperature=0.1
)
```

### 数据源优先级 (我们的环境)
1. **行情**: OKX API (已有) + YFinance (美股)
2. **新闻**: Tavily API (如已配置)
3. **情绪**: 可用 X/Twitter scraper (skills/x-tweet-fetcher)
4. **AI**: LiteLLM → DeepSeek/Qwen (成本控制)

### 推送渠道
- 已有: Telegram (当前通道)
- 可扩展: 飞书/Discord/企业微信

## 关键洞察 (Simons 评价)

1. **fail-open 设计** — 数据源不稳定不阻塞, 实战中很重要
2. **交易纪律内置** — 乖离率阈值 + 检查清单, 减少情绪交易
3. **LiteLLM 多模型路由** — 成本优化, 简单分析用便宜模型
4. **Agent 问股** — 多策略对话式分析, 适合非量化用户
5. **⚠️ 局限**: 依赖 LLM 判断质量, 无严格的概率/回测框架, 本质是"增强版看盘"而非量化系统

## 参考配置

```env
# 核心参数
STOCK_LIST=600519,hk00700,AAPL,TSLA
BIAS_THRESHOLD=5.0
NEWS_MAX_AGE_DAYS=3
NEWS_STRATEGY_PROFILE=short    # ultra_short/short/medium/long
REPORT_TYPE=full               # simple/full/brief
AGENT_MAX_STEPS=10
TRADING_DAY_CHECK_ENABLED=true
ENABLE_FUNDAMENTAL_PIPELINE=true
```

---
*蒸馏日期: 2026-05-01 | 原项目 440 commits, MIT License*
