# MEMORY.md — 小Quant 长期记忆
> 最后更新: 2026-03-17 00:07 CST

## 身份
- 小Quant（量子），AGI Super Team 首席交易官
- Telegram bot: @daniel_quant_bot | accountId: xiaoq
- 群组: Super Agents Center (-1003890797239)
- 报告双推: DailyNews群(-1003824568687, 用newsbot_send.py) + Super Agents群
- 模型: xingsuancode/claude-opus-4-6

## 账户
- 平台: Polymarket (polymarket.com)
- 登录邮箱: aaqwqaa68@gmail.com
- 浏览器: OpenClaw profile "openclaw" (browser优先，API备用)
- 初始资金: ~$56 (2026-02-26, Daniel充入50U)
- 当前资产: ~$33-36 (3/16, 累计ROI约-20%)
- 钱包: 0xd91eF877D04ACB06a9dE22e536765D2Ace246A9b (Polygon)

## 硬性目标（Daniel 3/16指定）
- **年化收益率 ≥ 50%** (参照梁文峰幻方量化水平)
- 月化 ~3.4%，日化 ~0.11%
- 以$35计算: 年底目标 ≥ $52.5

## 策略框架 (猎杀模式 v4.2)
- 🟢 S1 甜区主力 40%: **75-85¢**, <72h, Buffer>3%(3/15统一)
- 🔵 S2 趋势顺势 25%: BTC连续3h同向, 顺势方向
- 🟡 S3 事件驱动 15%: 重大新闻<2h, ≥2源确认
- 🟠 S4 套利 10%: Yes+No<$0.97
- ⚪ S5 波段管理: 涨30%卖半/涨50%全卖/亏25%止损
- ⚫ S6 临近结算: 结算前10-300秒, >95%确定性
- ⚡ S7 Elon推文: 结算前3-5h决策, xtracker计数, 仓位≤4%
- **核心**: 赚认知信息差的钱，数据>直觉，无edge不交易
- 自主交易上限: 单笔≤$20，>$20需Daniel确认

## 🩸 血泪教训（铁律）
- **地缘政治/军事盘永久禁入** — Iran两笔全损-$7.04
- **阶梯止损**: 亏>25%减仓40% | 亏>40%全部止损
- **趋势感知止损**: 亏>15%+4h连跌+buffer<3% → 止半保留半
- **cron买入必须过趋势关**: 4h≥3根跌=禁买YES。静态筛选≠可买！
- **BTC $68k教训(3/12)**: cron凌晨只看buffer+赔率就买，无视6h连续下跌→亏16%
- **反向longshot教训(3/14)**: 趋势禁YES就反向买NO@17¢→亏$1.76。买入边必须在75-90¢甜区！
- **视野盲区教训(3/13)**: 只扫BTC above盘，没发现GC/CL涨跌日盘。全品类都要扫！
- **CL $110教训(3/7)**: NO从84¢跌到46¢亏45%，未及时止损
- **加密阈值盘需>15%价格缓冲** — SOL $80仅6%缓冲→亏61%
- **下跌趋势中绝不买加密YES** — BTC>$72k buffer 2.3%→亏13.2%
- **永远保留$2+现金** — 3/5满仓$0.18锁死全天
- **>92¢绝不买** — 性价比太低
- **关联风险**: Iran恐慌波及所有加密资产

## 原则体系 (Dalio式)
- 已创建 `data/principles.md`，22条结构化原则(19条已验证)
- 分类: 入场(8条) + 禁区(4条) + 仓位(4条) + 止盈止损(6条) + 运营(4条)
- 每次犯错→提炼原则→写入→永不再犯

## 🤖 Bot思维 + 榜样体系 (3/15-16 重构)
### 传统量化榜样（Daniel 3/16 指定）
- **Jim Simons**: 文艺复兴大奖章年化66%(费前)，纯统计套利+信号处理
- **梁文峰**: 幻方量化→DeepSeek。2016.10从CPU线性模型→GPU深度学习，2017全面AI化
- **Ray Dalio**: 桥水，原则驱动。犯错→提炼原则→系统化
- **Ed Thorp**: 算牌鼻祖，Kelly公式实战第一人

### 顶尖交易Bot
- 98% Bot: $313→$414K，等确定性>0.20%偏移才入场
- Fully-Autonomous: 三模型投票+15层风控，53K lines
- NautilusTrader: 7阶段架构，信号融合+权重自学习

### Bot思维5条
1. 确定性优先（不猜，等数据确认）
2. 多信号融合（5-Gate系统）
3. 速度第一（cron每30min扫描）
4. 无情绪执行
5. 持续自学习

## 技能 & 工具（已掌握）
### 脚本
- `scripts/kelly_calculator.sh` — Kelly公式仓位计算器 ✅ (3/16实现)
- `scripts/backtest_5min.sh` — 5min盘回测器 ✅ (3/12实现)
- `scripts/backtest_5min_deep.sh` — 深度信号分解回测 ✅ (3/12)
- `scripts/scan_signals.sh` — 5min信号扫描器 v2.0
- `scripts/trend_analysis.sh` — BTC/ETH/SOL/GOLD 4h K线趋势
- `scripts/scan_markets.sh` — Polymarket市场扫描
- `scripts/entry_timing.sh` — RSI/MA20入场时机判断

### 关键技术知识
- Polymarket CLOB API: 价格/历史/订单簿查询
- Gamma API: `active=true&closed=false`必须加！
- Binance API: 1m K线数据获取
- 内置browser: Polymarket SPA页面数据获取（fbu不行）
- xtracker: Elon推文计数（browser读取）
- slug规律: `elon-musk-of-tweets-{period}`, `{ticker}-up-or-down-on-{month}-{day}-{year}`

## 5min盘回测发现 (3/12)
- **原策略(动量+EMA)完全无效**: 46.3%胜率，跑输随机
- **均值回归有edge**: 10min lookback $150阈值 → 59%胜率(n=61)
- **EV**: $0.36/笔(18%边际优势)
- **学术支撑**: Short-Term Reversal策略(Sharpe 0.816)的5min版本
- **状态**: 需7天纸盘验证 ⏳
- **Kelly计算**: 50¢+59%胜率 → 建议$3.15/笔(半Kelly)
- ⚠️ Kelly揭示: 85¢+80%胜率 = 负期望！需>85%胜率才有edge

## 学习计划 (3/16制定)
### 已研究
- 梁文峰/幻方量化方法论(从量化到DeepSeek完整路径)
- awesome-systematic-trading(97库+40+策略+55书)
- Freqtrade架构(FreqAI自适应训练)
- Microsoft QLib架构(RD-Agent LLM因子挖掘)

### 6项改进计划
1. **if/else → ML预测**: 本周数据集→下周scikit-learn→月底QLib
2. **Kelly精确化**: ✅ 已实现计算器脚本
3. **信息共享**: 每周同步市场洞察给团队
4. **Dalio式原则**: ✅ 已创建principles.md(22条)
5. **风控独立审计**: 日P&L推送[CFO]
6. **均值回归验证**: 7天纸盘进行中

### 关键工具待研究
- vectorbt: 快速向量化回测
- QLib/RD-Agent: AI量化+LLM因子挖掘
- Freqtrade/FreqAI: 自适应预测模型

## Cron任务 (活跃)
| 任务 | 频率 | 模型 |
|------|------|------|
| 全品类日盘猎杀 | 每30min | glm-5 |
| 仓位监控 | 每1h(xx:30) | m2.5 |
| Elon推文监控 | 21-03点每1h | m2.5 |
| 持仓日报 | 09:30 | m2.5 |
| 晚间盘点 | 20:00 | m2.5 |
| 夜间研究 | 1:30/3:30/5:30 | opus |
| 每日反思 | 23:15 | glm-5 |
| 周度回顾 | 周一10:00 | glm-5 |
⚠️ 猎杀数据可能过期(最新3/8)，需检查cron实际运行状态

## 团队宪章要点 (3/16阅读)
- 使命: 构建超越99% AI团队的AGI原生组织
- 决策层级: L0 Daniel → L1 CEO CEO → L2 C-Suite(我)
- 核心原则: 第一性原理 + 信息流动>孤岛 + 记忆即生命 + 质量>数量
- QMD知识库: 交易前查询，重要发现写入
- 汇报规范: 简洁有料≤500字，详细写文件给摘要+路径

## Agent团队
| Agent | accountId | 职责 |
|-------|-----------|------|
| CEO CEO | default | 主调度、项目推进 |
| Jensen | xiaoops | 运维、部署 |
| [CDO] | xiaodata | 数据信息、X监控、链上 |
| [CRO] | xiaoresearch | 调研、分析 |
| [CFO] | xiaofinance | 财务相关 |
| [CCO] | - | 内容生成 |
| Finn | - | 代码开发 |

**跨Agent通信**: sessions_send(sessionKey="agent:xxx:telegram:group:-1003890797239")

## 数据协作
- [CDO]负责: X监控、链上数据、新闻API
- 数据需求都找[CDO]
- 报告发DailyNews群用newsbot_send.py
- Daniel考虑把我做成24h量化bot产品(用户30%/Daniel70%)

## Polymarket技术备忘
- 登录状态: ✅ (3/1 Daniel授权)
- 浏览器交易: click输入框→type金额→click Buy→等几秒确认
- Gamma API: 必须加`active=true&closed=false`获取活跃市场
- Elon推文盘API搜不到，只能slug直查
- fbu不能用于SPA页面(只拿loading skeleton)，必须用内置browser
- gateway token mismatch: 重启后需重新同步
