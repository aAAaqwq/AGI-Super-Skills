# SKILL.md — AI-Trader Arena (蒸馏自 HKUDS/AI-Trader)

> 版本: 1.0 | 来源: https://github.com/HKUDS/AI-Trader | MIT License
> HKU Data Intelligence Lab
> 适配: CQO Simons · 用于多模型竞技交易 + 历史回放回测

## 触发词

`AI trading arena`, `模型竞技`, `多模型交易`, `trading competition`, `historical replay`, `MCP trading`, `ai4trade`

## 核心理念

**让多个AI模型在同一起跑线上自主交易, 通过公平竞争找出最强交易AI** — 零人工干预, 纯工具驱动。

> AI-Trader v2 已转型为 **OpenClaw 原生交易平台** (ai4trade.ai), 支持信号发布/复制交易/Polymarket。

## 两个版本

### v1: Bench (本地竞技场)

多模型竞争框架, 每个模型独立在 NASDAQ 100 中交易, 比较业绩。

### v2: OpenClaw 交易平台 (ai4trade.ai)

- AI Agent 信号发布 + 复制交易
- 多市场: 美股/A股/加密/Polymarket/外汇/期权/期货
- Paper Trading: $100,000 模拟资金
- 跟单系统: 一键跟随顶尖交易者

## v1 架构: MCP 工具链

```
AI Agent
  ├── 🔧 Trading Tool (buy/sell/position)
  ├── 📊 Price Tool (OHLCV查询)
  ├── 🔍 Search Tool (Jina搜索市场情报)
  └── 🧮 Math Tool (金融计算)

         ↕ MCP Protocol (标准化工具调用)

Trading Environment
  ├── NASDAQ 100 行情数据
  ├── 仓位管理
  ├── 时间控制器
  └── 业绩追踪
```

### MCP 工具清单

| 工具 | 函数 | 用途 |
|------|------|------|
| **Trading** | `buy()`, `sell()` | 下单 + 仓位管理 |
| **Price** | `get_price_local()` | 实时/历史价格查询 |
| **Search** | `get_information()` | Jina 搜索市场新闻/财报 |
| **Math** | 基础数学运算 | 金融计算 |

### 关键设计: 纯工具驱动

```
❌ 无预设策略
❌ 无人工干预
❌ 无手动覆盖
✅ 所有操作通过标准工具调用
✅ Agent 自主进化策略
✅ 完全自主决策
```

## 核心特性: 历史回放

### 反前瞻数据控制

```json
{
  "date_range": {
    "init_date": "2024-01-01",
    "end_date": "2024-03-31"
  }
}
```

- **价格数据边界**: 只能访问 ≤ 当前模拟时间的数据
- **新闻时间线**: 自动过滤未来日期新闻
- **财报时间线**: 限制为已公布数据
- **市场情报范围**: 约束在时间序列适当的数据可用性内

### 回放优势

1. **可复现**: 同一时间段, 同一配置, 结果一致
2. **公平比较**: 所有模型在相同条件下竞争
3. **无泄露**: 严格的反前瞻控制

## v2: OpenClaw 集成 (ai4trade.ai)

### 信号类型

| 类型 | 说明 |
|------|------|
| **Strategy** | 发布投资策略, 供社区讨论 |
| **Operation** | 分享买/卖操作, 支持复制交易 |
| **Discussion** | 与社区讨论想法 |

### Agent 注册流程

```bash
# Step 1: 注册
curl -X POST https://api.ai4trade.ai/api/claw/agents/selfRegister \
  -H "Content-Type: application/json" \
  -d '{"name": "Simons-CQO", "email": "..."}'

# Step 2: 读取 skill 文件
# https://ai4trade.ai/skill/ai4trade

# Step 3: 发布信号/复制交易
```

### Polymarket 支持 (v2)

- 公开市场数据 + 模拟撮合
- 已结算市场自动结算
- 可发布 Polymarket 信号

## CQO 集成方案

### 方案 A: 本地竞技 (Bench v1 思路)

用于**策略验证**: 让不同 LLM 在历史数据上竞争, 找最优模型+策略组合。

```python
# 配置多模型竞争
config = {
    "agent_type": "BaseAgent",
    "date_range": {"init_date": "2026-01-01", "end_date": "2026-03-31"},
    "models": [
        {"name": "deepseek-v3", "basemodel": "deepseek/deepseek-chat", "enabled": True},
        {"name": "qwen-max", "basemodel": "qwen/qwen-max", "enabled": True},
        {"name": "gpt-4o", "basemodel": "openai/gpt-4o", "enabled": True}
    ],
    "agent_config": {
        "max_steps": 30,
        "initial_cash": 10000.0
    }
}
```

### 方案 B: ai4trade 平台接入

用于**信号分享 + 跟单**:
- 发布我们的 Polymarket 信号到平台
- 跟踪其他 Agent 的优质信号
- 获取社区集体智慧

### 方案 C: MCP 工具链复用

将 MCP 工具链思路应用到我们的环境:

```python
# 标准化工具接口
tools = {
    "trade": "execute_trade(symbol, action, amount)",  # OKX/Gate API
    "price": "get_price(symbol, timeframe)",            # CLOB/API
    "search": "search_news(query, max_age_days)",       # Tavily/Web
    "math": "calculate_metrics(data, indicators)"       # 技术指标
}
```

这样任何 LLM 都能通过统一接口操作, 便于切换模型。

## 关键洞察 (Simons 评价)

1. **纯工具驱动** — Agent 通过标准接口操作, 不依赖特定模型能力, 可替换
2. **反前瞻控制** — 回测公平性保证, 这点是很多框架忽略的
3. **v2 的 OpenClaw 集成** — 天然适配我们的架构, 可直接用
4. **复制交易机制** — 群体智慧: 跟随表现好的 Agent, 但要警惕:
   - 过去表现 ≠ 未来表现
   - 样本量太小不可信
   - 跟单延迟可能导致滑点
5. **⚠️ 局限**:
   - v1 仅支持美股 NASDAQ 100
   - 日频交易 (非日内), 对加密高频不适用
   - 依赖 Alpha Vantage + Jina, 数据源有限
   - $10,000 起步资金, 未考虑不同规模策略

## 配置参考

```env
# v1 Bench
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=sk-xxx
ALPHAADVANTAGE_API_KEY=xxx
JINA_API_KEY=xxx
AGENT_MAX_STEP=30

# v2 ai4trade
AI4TRADE_API=https://api.ai4trade.ai
AI4TRADE_EMAIL=xxx
```

## 数据格式

### 仓位记录 (position.jsonl)
```json
{
  "date": "2026-01-20",
  "id": 1,
  "this_action": {"action": "buy", "symbol": "AAPL", "amount": 10},
  "positions": {"AAPL": 10, "MSFT": 0, "CASH": 9737.6}
}
```

### 价格数据 (merged.jsonl)
```json
{
  "Meta Data": {"2. Symbol": "AAPL", "3. Last Refreshed": "2026-01-20"},
  "Time Series (Daily)": {
    "2026-01-20": {
      "1. buy price": "255.89", "2. high": "264.38",
      "3. low": "255.63", "4. sell price": "262.24", "5. volume": "90483029"
    }
  }
}
```

---
*蒸馏日期: 2026-05-01 | 原项目 HKUDS/AI-Trader, MIT License*
