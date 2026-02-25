# Polymarket 量化投资系统

真实交易系统，$3 本金在 Polymarket 预测市场上执行量化策略。

## 概述

- **模式**: 真实交易（非模拟盘）
- **本金**: $3 USDC (Polygon)
- **策略**: 高确定性套利 + CME 套利 + 事件驱动
- **推送**: DailyNews 群 (@fkkanfnnfbot → -1003824568687)
- **负责 Agent**: quant（量化投资专员）
- **协作**: finance（资金核算）、research（情报）、news（新闻）

## 核心策略

### 1. 高确定性 No (60% 仓位 ~$1.80)
- 买入短期内极不可能发生事件的 No
- 条件: No ≥ 85%, 剩余 ≤ 60 天
- 预期: 15-25% 年化

### 2. CME 套利 (20% 仓位 ~$0.60)
- Polymarket vs CME FedWatch 利率预期价差
- 条件: 价差 > 5%
- 预期: 低风险稳定

### 3. 事件驱动 (20% 仓位 ~$0.60)
- 基于新闻情报的信息优势交易
- 需要 research/news 支持
- 中风险高回报

## 风控

| 规则 | 值 |
|------|------|
| 单笔上限 | $1 |
| 最少分散 | 3 个市场 |
| 止损线 | 赔率反向 15% |
| 总本金 | $3 |

## 交易 SOP (标准化操作流程)

```
┌─────────────────────────────────────────────────────────────┐
│  Polymarket 量化交易完整 SOP                                 │
│  版本: 1.0 | 更新: 2026-02-22                               │
└─────────────────────────────────────────────────────────────┘

步骤 1: 分析现有资产
├── 检查钱包余额 (USDC native)
├── 检查 Polymarket 账户余额
├── 检查现有持仓状态
└── 输出: 资产报告

步骤 2: 结合数据源 [协作: 小data]
├── 扫描目标市场 (Fed、Crypto、Politics)
├── 获取最新赔率快照
├── 对比 CME/CryptoCompare 数据
└── 输出: 机会列表 (按置信度排序)

步骤 3: 检查/充值余额 ⚠️ 关键步骤
├── 如 Polymarket 余额 < 交易金额:
│   ├── native USDC → USDC.e (QuickSwap)
│   └── 存款到 Polymarket
└── 输出: 可用余额确认

步骤 4: 按策略分配资产
├── 读取 config/adaptive_strategy.json
├── 计算各市场分配比例
├── 验证风控规则 (单笔≤$1, 分散≥3市场)
└── 输出: 交易计划

步骤 5: 执行交易建仓 [工具: browser-use]
├── 打开 Polymarket 市场页面
├── 选择正确选项 (Yes/No)
├── 输入金额，确认交易
├── 获取交易哈希
└── 输出: 交易确认

步骤 6: 记录交易
├── 写入 data/trade_log.json
├── 更新 data/portfolio.json
└── 输出: 交易记录

步骤 7: 监控仓位
├── 定时检查持仓状态 (每4h)
├── 赔率变动告警 (>5%)
├── 到期提醒
└── 输出: 监控报告

步骤 8: 反馈收仓
├── 事件结束后检查结果
├── 计算盈亏
├── 更新策略参数
└── 输出: 收仓报告

协作分工:
- 小quant: 执行交易、仓位管理
- 小data: 数据采集、市场扫描
- 小finance: 资金核算、盈亏计算
- 小a: 策略设计、SOP 优化
```

## 常见问题排查

### 交易按钮显示 "Deposit"
**原因**: Polymarket 账户余额为 $0
**解决**: 
1. 检查钱包是否有 USDC (native)
2. 兑换 native USDC → USDC.e
3. 在 Polymarket 存款

### Gateway 超时
**原因**: WebSocket 连接问题
**解决**: 直接执行脚本，绕过 agent 调度

## 浏览器自动化工具

### 推荐使用 browser-use ⭐

**browser-use** 是 AI 驱动的智能浏览器自动化工具，比传统 Playwright 更智能：

| 特性 | browser-use | Playwright | browser tool |
|------|-------------|------------|--------------|
| 智能决策 | ✅ AI 自动决策 | ❌ 需预编程 | ✅ AI 辅助 |
| 适应性 | ✅ 自动适应页面变化 | ❌ 页面变化需重写 | ✅ 自动适应 |
| Token 消耗 | 🟢 ~2000-4000 | 🟡 ~1000-2000（需调试） | 🔴 ~5000-10000 |
| 维护成本 | 🟢 低 | 🔴 高 | 🟡 中 |
| 适合定时任务 | ✅ | ✅ | ❌ |
| Chrome 支持 | ✅ | ✅ | ✅ |

**安装状态**:
- ✅ browser-use 0.11.11
- ✅ browser-use-sdk 2.0.15
- ✅ langchain-openai

## 文件结构

```
skills/polymarket-profit/
├── SKILL.md              # 本文件
├── config/
│   ├── markets.json      # 关注市场列表
│   └── strategies.json   # 策略配置
├── scripts/
│   ├── browser_use_trader.py  # ⭐ browser-use 智能交易（推荐）
│   ├── playwright_trader.py   # Playwright 交易（备用）
│   ├── fetcher.py        # Polymarket 数据抓取
│   ├── analyzer.py       # 机会分析引擎
│   └── trader.py         # API 交易模块
├── data/
│   ├── odds/             # 赔率历史快照 (JSONL)
│   ├── portfolio.json    # 当前持仓
│   ├── trade_log.json    # 交易日志
│   └── reports/          # 投资报告
└── templates/
    └── daily_report.md   # 推送模板
```

## 使用

### browser-use 智能交易（推荐）

```bash
# 检查市场状态
python3 ~/clawd/skills/polymarket-profit/scripts/browser_use_trader.py check --market fed-decision-in-march-885

# 执行交易（买入 $0.50 的 No，价格条件 ≥ 0.85）
python3 ~/clawd/skills/polymarket-profit/scripts/browser_use_trader.py trade \
  --market fed-decision-in-march-885 \
  --action buy_no \
  --amount 0.5 \
  --price 0.85

# 查看持仓
python3 ~/clawd/skills/polymarket-profit/scripts/browser_use_trader.py portfolio

# 显示浏览器（调试用）
python3 ~/clawd/skills/polymarket-profit/scripts/browser_use_trader.py check --show
```

### 传统脚本

```bash
# 查看持仓
python3 scripts/trader.py status

# 健康检查
python3 scripts/trader.py health

# 生成交易指令
python3 scripts/trader.py instruction --market <slug> --outcome No --amount 0.6 --price 0.85
```

## 交易流程

1. quant agent 每日分析赔率快照 → 生成交易建议
2. 推送到 DailyNews 群
3. 用户确认 → 执行交易（网页手动 或 API 自动）
4. 记录到 trade_log.json + portfolio.json
5. finance agent 每周核算盈亏

## 前置条件

- [x] Polymarket 账户（钱包登录）✅
- [x] 钱包私钥已存储 (`pass show api/polymarket-wallet`) ✅
- [x] MATIC 充足 (0.31) ✅
- [ ] $3 USDC 在 Polygon 网络 ⏳ (当前 $0.00)
- [x] Python venv 环境 ✅
- [x] py-clob-client 已安装 ✅

## 定时任务

| 任务 | Cron | 推送目标 | 状态 |
|------|------|----------|------|
| 每日报告 | 8:00 | DailyNews 群 | ✅ |

## 钱包信息

| 项目 | 值 |
|------|------|
| 地址 | `0xd91eF877D04ACB06a9dE22e536765D2Ace246A9b` |
| 网络 | Polygon (137) |
| MATIC | 7.34 (~$2.50) |
| USDC (native) | $2.01 ✅ |
| USDC.e (bridged) | $0.00 |

### ⚠️ 重要：Polygon 上有两种 USDC

| 类型 | 合约地址 | Polymarket 支持 |
|------|----------|----------------|
| USDC (native) | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` | ❌ 需兑换 |
| USDC.e (bridged) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` | ✅ 直接使用 |

**交易前需要**：native USDC → USDC.e 兑换

**⚠️ 安全**: 私钥已通过 pass 安全存储，但建议轮换（曾在群组暴露）

## 使用

```bash
# 生成每日报告
python3 ~/clawd/skills/polymarket-profit/scripts/generate_report.py

# 手动推送报告（通过 OpenClaw）
# 使用 message 工具发送到 chat_id: -1003824568687

# 查看持仓
cat ~/clawd/skills/polymarket-profit/data/portfolio.json

# 查看交易日志
cat ~/clawd/skills/polymarket-profit/data/trade_log.json
```
