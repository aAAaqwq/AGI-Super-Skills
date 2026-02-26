# Polymarket 量化交易 SOP

## 概述
系统性的 Polymarket 预测市场量化交易体系。浏览器自动化 + API 双通道。
核心策略：**三层跟风交易系统** — 跟随市场共识+波段管理，短期复利。

---

## 🧠 三层跟风策略体系（Daniel v2）

### 核心思想
不预测市场，跟随市场共识赚钱。市场大多数人的判断在短期内（1-3天结算）胜率极高。

### 策略一：稳健跟风（70%资金）🟢
**逻辑：** 找当天或3天内结算的热门event，跟大多数人投。

| 参数 | 标准 |
|------|------|
| **选盘** | 当天/3天内结算，24h vol > $100K |
| **方向** | 跟大多数人：选70-80%概率方向的Yes或No |
| **入场** | 最佳区间：买入80-92¢（回测甜区85-95¢胜率100%） |
| **止损** | 跌破70¢割肉 |
| **止盈** | Hold到结算，收割100¢ |
| **单笔** | 总资金10-15% |
| **预期** | 每笔赚8-25%，胜率>85% |

**回测结果（近期50个已结算市场）：**
- 85-95¢区间：3/3胜率100%，平均+13.5%/笔 ✅ 最优
- 70-85¢区间：4/6胜率67%，平均-13.8%/笔 ❌ 赔率不够覆盖亏损
- ≥90¢区间：7/8胜率88%，但平均-10.8%/笔 ⚠️ 需93%+胜率才盈亏平衡

**关键教训：** 70-85¢太危险（1次亏损抵消3次盈利），≥95¢利润太薄。**80-92¢是甜区。**
⚠️ 排除体育赛事！体育盘70-85¢的爆冷率太高。优先选：加密阈值、地缘政治、经济数据。

---

### 策略二：逆向少数派精选（20%资金）🟡
**逻辑：** 在多选项event中，找整体少数派方向，选该方向中概率最高的选项。

**举例（Elon推文盘）：**
- 整体看：买Yes的人均80-90%，买No的人均不超50%
- Yes是多数派，No是少数派 → 选No方向
- No方向中各区间：260-279@10%, 280-299@6%, 300-319@26%, 320-339@37%
- 不对——应该看哪个No概率最高。实际上每个区间的No=1-Yes
- 简化：**选概率最高的那个选项Yes**（如320-339@37%），因为它在多选项中是"少数派中的多数"

**正确理解：**
1. 看整体Yes/No总量：哪边总投入少 = 少数派方向
2. 选少数派方向中，概率最大的那个选项
3. 如整体No方总投入少，在No的各选项中选概率最高的
4. 如整体Yes方总投入少，在Yes的各选项中选概率最高的

| 参数 | 标准 |
|------|------|
| **选盘** | 多选项event（区间盘、多选一盘） |
| **方向** | 整体少数派方向（Yes/No总量对比） |
| **入场** | 该方向中概率最高的选项（通常25-40¢） |
| **止损** | 亏50%或逻辑证伪 |
| **止盈** | 涨50%即可卖出锁利，不必hold到结算 |
| **单笔** | $3-5（总资金5-9%） |
| **预期** | 每笔赚50%+，胜率40-55% |

---

### 策略三：波段止损/实验性高风险（10%资金）🔴
**逻辑：** 买入后利用价格波动在中途高点卖出，减少回撤。作为实验性策略，严格记录每笔交易结果用于复盘优化。

**适用场景：**
1. 已持仓大概率要归零 → 在波动高点sell出，回收部分资金
2. 价格短期暴涨但离结算还远 → 先卖锁利，等回调再买

| 操作 | 条件 |
|------|------|
| **K线高点卖出** | 价格接近该市场历史K线最高点且盈利 → 卖出 |
| **波段卖出** | 持仓涨>30%且离结算>24h → 卖50% |
| **止损卖出** | 基本面转向+亏>30% → 全卖 |
| **回调买回** | 卖出后跌回支撑位 → 可再买入 |
| **临近到期** | 结算前4h内不做波段，hold到底 |

**盯盘频率：** 每30分钟检查持仓价格变动（cron任务已设）

**实验记录要求：**
每笔波段交易必须记录到 trades/swing-log.md：
- 买入时间/价格/理由
- 卖出时间/价格/触发条件
- 盈亏金额和百分比
- 复盘：判断对了什么/错了什么
- 每周汇总波段策略胜率和收益

---

### 决策流程图
```
发现热门event（当天/3天结算）
  │
  ├─ 二选一盘（Yes/No）→ 策略一：买80-92¢共识方向（70%资金）
  │
  ├─ 多选项盘（区间/多选一）→ 策略二：少数派方向中概率最高选项（20%资金）
  │
  └─ 已持仓管理 → 策略三：波段止损/实验性操作（10%资金）
```

### 每日复利目标
- 策略一（70%）：稳定5-10%/天（复利核心引擎）
- 策略二（20%）：爆发50%+/笔（提升整体收益）
- 策略三（10%）：实验性波段，严格记录（减亏+学习）
- **综合目标：日均净收益5%+，月复利翻倍**

---

## 🔑 浏览器自动化策略

**根据场景选择工具：**

| 场景 | 工具 | 原因 |
|---|---|---|
| Polymarket 交易操作 | **内置 browser**（openclaw profile） | Web3 认证（Magic Link）依赖 IndexedDB，需完整 Chrome profile |
| 简单页面抓取/截图 | **fast-browser-use** | Rust 引擎，启动快、省内存、token 效率高 |
| 需要 cookie 认证的站点 | **fast-browser-use** + `--load-session` | 轻量级 cookie 注入即可 |
| 需要 IndexedDB/localStorage 认证 | **内置 browser** | 需要完整 profile 保持状态 |

### 内置 Browser 操作模板（Polymarket 专用）

**Token 优化技巧：**
- `snapshot(compact=true, maxChars=3000)` — 限制输出大小
- `selector` 参数 — 只抓需要的 DOM 区域
- `evaluate` — 直接跑 JS 提取结构化数据，跳过 DOM 解析
- 优先用 API 获取数据，browser 仅用于需要登录态的操作（下单/查仓位详情）

```
# 启动（已有登录态，无需重复登录）
browser start profile=openclaw

# 导航
browser navigate targetUrl="https://polymarket.com/portfolio" profile=openclaw

# 精简快照（省 token）
browser snapshot compact=true maxChars=3000 profile=openclaw

# JS 直接提取数据（最省 token）
browser act kind=evaluate fn="() => JSON.stringify({...})" profile=openclaw

# 截图（需要视觉确认时）
browser screenshot profile=openclaw

# 点击/输入
browser act kind=click ref=eXX profile=openclaw
browser act kind=fill ref=eXX text="1.00" profile=openclaw
```

**登录态位置：** `~/.openclaw/browser/openclaw/user-data/` （Chrome profile，自动持久化）

**页面跳转：** `browser navigate` 经常超时！用以下方式更稳定：
```
browser act kind=evaluate fn="() => { window.location.href='URL'; return 'ok'; }" profile=openclaw
# 或
browser open targetUrl="URL" profile=openclaw  # 新tab
```

**交易面板操作要点：**
- 点event列表的"Buy Yes/No"按钮 → 打开右侧面板（默认市价单）
- 面板中：Buy/Sell radio → Yes/No radio → 金额输入 → 确认按钮
- **直接输金额走市价单！不要切限价！** 小资金没必要省那1-2¢

---

## 💰 资金配置策略：70/20/10 三层跟风

### 🟢 低风险层（70% 资金）— 稳健跟风

**目标：** 高确定性稳定收益，胜率 > 90%

| 参数 | 标准 |
|------|------|
| **入场价格** | ≥ 90¢（隐含概率≥90%） |
| **市场类型** | 宏观数据、已知日程事件、技术边界 |
| **单笔上限** | 总资金 15% |
| **同类敞口** | ≤ 35% |
| **止损** | 跌破 80¢ + 基本面恶化 |
| **止盈** | 持有至到期，目标100¢ |
| **预期收益** | 3-10%/笔（年化20-50%） |
| **到期** | 3-30天 |

**操作规则：** 买入后hold到结算，不做波段。回测验证+EV ≥ 1.5%。

---

### 🟡 中风险层（20% 资金）— 逆向少数派精选

**目标：** 有分析依据的事件驱动交易，收益15-30%

| 参数 | 标准 |
|------|------|
| **入场价格** | 75¢-89¢（隐含概率70-89%） |
| **市场类型** | 地缘政治、政策博弈、情绪边界事件 |
| **单笔上限** | 总资金 9%（≤$5） |
| **止损** | 入场价 -15¢（如83¢→止损68¢） |
| **止盈** | 75%持有至到期，25%在95¢+减仓 |
| **预期收益** | 15-30%/笔 |
| **到期** | 7-45天 |

**选市硬性标准（必须全部满足）：**
- [ ] 价格在 75¢-89¢ 区间
- [ ] 流动性 > $5,000
- [ ] 有**明确的反向催化剂**：为什么市场高估了概率？
- [ ] 事件有**历史先例**可参考
- [ ] 信息不对称来源**可验证**
- [ ] 不与现有持仓高度相关

**入场流程：**
1. 写下"为什么市场错了"（1-2句，必须）
2. 计算：胜率×收益 - 败率×亏损 > 0
3. 设定止损价（入场价 -15¢）
4. 单笔 = min($5, 中风险剩余额度的30%)

**持仓管理：**
- 每3天检查基本面变化
- "为什么市场错了"论据消失 → 无论盈亏立即出场
- 盈利 >10¢ 后 → 止损上移至成本价（保本止损）
- **禁止补仓摊成本**

**排除清单：**
- ❌ 仅凭价格便宜（没有基本面依据）
- ❌ 恐慌反转（回测-89%！）
- ❌ 距到期 <5天且价格仍在75¢以下
- ❌ 同一主题已有持仓

---

### 🔴 高风险层（10% 资金）— 波段实验

**目标：** 小注博大，单笔2x-3x回报

| 参数 | 标准 |
|------|------|
| **入场价格** | 40¢-74¢（隐含概率40-74%） |
| **市场类型** | 黑天鹅对冲、逆势反转、低估事件 |
| **单笔上限** | $3（总资金5%，严格上限） |
| **止损** | 入场价 -20¢ 或亏损超$2 |
| **止盈** | 目标80¢+出场（2x-3x） |
| **预期收益** | 50-150%（或归零） |
| **到期** | 7-60天 |

**硬性规则：** 单笔最大$3，总层级不超配额，**禁止补仓**。

**卖出阶梯：**
- 📈 涨100%（翻倍）→ 卖50%锁利
- 📈 涨200%（3x）→ 再卖50%
- 📉 亏60%或逻辑证伪 → 清仓
- ⏰ 持有>30天无变化 → 评估

---

### 📊 资金分配（$55 为例）

| 仓位类型 | 分配 | 策略 |
|---|---|---|
| 🟢 稳健跟风 | $38.5 (70%) | 3-5笔 80-92¢ 跟共识方向 |
| 🟡 少数派精选 | $11.0 (20%) | 2-3笔 25-40¢ 少数派方向最高概率 |
| 🔴 波段实验 | $5.5 (10%) | 1-2笔 波段操作，严格记录 |

### 💰 盈利流动规则
```
低风险到期盈利 → 50%留低风险再投，50%补充现金池
中风险到期盈利 → 60%转入低风险，40%留中风险
高风险到期盈利 → 50%转低风险，30%转中风险，20%留高风险
```

### 📉 亏损控制
```
单层亏损 >20% → 暂停该层新开仓，分析原因
高风险层归零 → 从低风险利润补充，上限$3/次
中风险连续2笔亏损 → 检查选市标准
资金跌至$40 → 降至两层（75%低+25%中，暂停高风险）
```

### 🔄 月度目标
- 低风险：月收益 3-5%
- 中风险：月收益 8-12%
- 高风险：不设目标，只设亏损上限
- 资金增长至$70 → 重新按50/30/20分配

### 🎯 快速决策卡
```
看到新市场时，问3个问题：
1. 价格在哪个区间？→ 决定层级
2. 我能说出"为什么市场错了"吗？→ 决定是否入场
3. 亏完这笔能睡着吗？→ 决定仓位大小
```

---

## SOP 自动化流程

### Step 1: 持仓盘点
```
# 方式A: API（首选，零 token 浏览器开销）
GET https://gamma-api.polymarket.com/markets → 配合钱包地址查持仓

# 方式B: 内置 browser（需要详细信息时）
browser navigate targetUrl="https://polymarket.com/portfolio" profile=openclaw
browser snapshot compact=true maxChars=3000 profile=openclaw
# 输出 → reports/portfolio-snapshot.md
```

### Step 2: 市场扫描（双轨制）

**稳健扫描：**
```
GET https://gamma-api.polymarket.com/markets?active=true&closed=false&order=volume24hr&ascending=false&limit=50
筛选: outcomePrices[0] >= 0.90, volume24hr > 100000, 到期3-30天
标记: 🟢 稳健机会
```

**猎手扫描：**
```
同一 API 数据
筛选: 0.10 <= outcomePrices[0] <= 0.40, volume24hr > 50000, 到期7-60天
交叉验证: web_fetch 相关新闻，确认是否有信息优势
标记: 🔴 猎手机会
```

### Step 3: 策略分析

**稳健仓评估：**
- 市场共识 ≥ 90% 的合理性验证
- 检查结算规则是否有模糊条款
- 计算年化收益率：(1/price - 1) × (365/到期天数)
- 年化 > 30% 才值得锁仓

**猎手仓评估：**
- 必须有明确的 **信息优势论述**（不是"我觉得"）
- 风险回报比 ≥ 3:1
- 检查历史价格走势（是在涨还是跌？）
- oneWeekPriceChange 方向是否支持判断

### Step 4: 交易执行（内置 browser）— 市价单优先！

**核心原则：直接输金额，市价成交，不搞限价单！**

限价单多一堆操作（切限价→改价→输份额），还可能挂不上。$2的小单直接市价梭哈。

```
# 1. 打开event页面（用JS跳转，避免navigate超时）
browser act kind=evaluate fn="() => { window.location.href='https://polymarket.com/event/xxx'; }" profile=openclaw
sleep 3-5s

# 2. 点击目标子市场的按钮（如"Buy No 83¢"）
#    → 右侧交易面板会自动打开，默认市价单模式
browser act kind=click ref=eXX profile=openclaw

# 3. 确认面板已选对方向（Yes/No radio），如果不对就点切换
browser snapshot compact=true maxChars=800 selector="radiogroup" profile=openclaw

# 4. 直接在金额框输入金额（如$2）
browser act kind=click ref=e_amount profile=openclaw
browser act kind=type ref=e_amount text="2" profile=openclaw

# 5. 点"买入"按钮确认
browser act kind=click ref=e_buy profile=openclaw

# 6. 快照确认成交
sleep 2
browser snapshot compact=true maxChars=1000 profile=openclaw
```

**⚠️ 注意事项：**
- event列表页的"Buy Yes/No XX¢"按钮只是**打开交易面板**，不会自动下单
- 面板默认是**市价单(Market)**模式 — 这正是我们要的！
- 金额输入框placeholder是"$0"，直接输数字即可
- `browser navigate` 常超时 → 用 `evaluate + window.location.href` 更稳定
- 中文版URL: `/zh/event/...`  英文版: `/event/...` 都能用

### Step 5: 卖出/平仓
```
# 稳健仓：一般 hold 到结算，除非黑天鹅
# 猎手仓：按止盈阶梯执行

browser navigate targetUrl="https://polymarket.com/portfolio" profile=openclaw
browser snapshot compact=true maxChars=3000 profile=openclaw

# 检查每个猎手仓位：
# - 涨100%？→ 卖50%
# - 涨200%？→ 再卖50%
# - 亏60%？→ 清仓
# - 持有>30天无变化？→ 评估

browser act kind=click ref=eXX profile=openclaw   # 点 Sell
browser act kind=fill ref=eXX text="X" profile=openclaw
browser act kind=click ref=eXX profile=openclaw   # 确认卖出
# 记录 → trades/trade-log.md 更新状态
```

---

## 仓位规则汇总

| 规则 | 低风险 🟢 | 中风险 🟡 | 高风险 🔴 |
|---|---|---|---|
| 资金占比 | 50% | 30% | 20% |
| 单笔上限 | 总资金 15% | 总资金 9%（≤$5） | $3（总资金5%） |
| 同类敞口 | ≤ 35% | 不与现有仓相关 | ≤ 15% |
| 目标价格 | ≥ 90¢ | 75¢-89¢ | 40¢-74¢ |
| 持仓周期 | Hold 到结算 | 7-45天，主动管理 | 7-60天，阶梯止盈 |
| 止损 | 跌破80¢+基本面恶化 | 入场价-15¢ | 入场价-20¢或亏$2 |
| 止盈 | 结算收割 | 75%到期+25%@95¢减仓 | 80¢+出场（2-3x） |
| 入场要求 | EV≥1.5% | 必须写"为什么市场错了" | 赔率>2:1+催化剂 |

## 风控红线
- ❌ 不理解结算规则不下注
- ❌ 不All-in / 不追涨杀跌
- ❌ 低流动性不大额建仓
- ❌ 猎手仓无信息优势不下注
- ✅ 每笔必有止损位 + 数据支撑
- ✅ 稳健仓年化 < 30% 不值得锁仓
- ✅ 猎手仓风险回报比 < 3:1 不下注

---

## 🔍 每日 Event 机会发现流程

### 核心思路
每天主动扫描 Polymarket 上 24-48h 内到期的市场，寻找有信息优势的下注机会。

### Step 1: 拉取近期到期市场
```bash
# 拉取所有活跃市场，按24h交易量排序
curl -s 'https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=200&order=volume24hr&ascending=false' > /tmp/pm_scan.json
```

### Step 2: 筛选 24-48h 内到期 + 可负担
```python
import json
from datetime import datetime

with open('/tmp/pm_scan.json') as f:
    data = json.load(f)

now = datetime.utcnow()
for m in data:
    prices = json.loads(m.get('outcomePrices', '[]'))
    if not prices: continue
    yes_p = float(prices[0])
    end = m.get('endDate', '')
    if not end: continue
    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
    hours_left = (end_dt - now.replace(tzinfo=end_dt.tzinfo)).total_seconds() / 3600
    if hours_left < 0 or hours_left > 48: continue

    vol24 = m.get('volume24hr', 0)
    if vol24 < 10000: continue  # 最低流动性

    # 提取 event 级别链接
    events = m.get('events', [])
    event_slug = events[0]['slug'] if events else m.get('slug', '')
    event_title = events[0]['title'] if events else m['question']
    link = f'https://polymarket.com/event/{event_slug}'

    print(f'{event_title} | Yes@{yes_p:.2f} | {hours_left:.0f}h | ${vol24/1000:.0f}k')
    print(f'  {link}')
```

### Step 3: 按主题分类评估

**可分析型（有信息优势）：**
- 🐦 **Musk 推文数量盘** → 去 X/Nitter 数推文，精准估算区间
- ₿ **BTC 价格阈值盘** → 查当前价+趋势，判断是否能到
- 📊 **经济数据盘** → 查已发布的数据，可能价格未反映
- 🗳️ **政治事件盘** → 查最新新闻，判断事件是否已发生

**纯赌博型（无信息优势，跳过）：**
- 🎮 电竞比赛
- ⚽ 体育赛事（除非你懂球）
- 🎲 纯随机事件

### Step 4: 深度调研有优势的盘
```
对每个有潜力的盘：
1. web_fetch 相关新闻/数据源
2. 计算 AI 概率 vs 市场定价
3. 偏差 ≥ 5% → 标记为机会
4. 输出：市场链接 + 方向 + 理由 + 建议金额
```

### Step 5: 输出格式
```
📊 每日机会扫描 [日期]

━━ 🎯 有优势的机会 ━━
① [主题名称] — [到期时间]
   链接: https://polymarket.com/event/xxx
   方向: Buy Yes/No @ XX¢
   理由: [信息优势论述]
   建议: $X（占资金X%）

━━ ⏭️ 观察中 ━━
② [主题名称] — 需要更多信息
   链接: ...

━━ ❌ 跳过 ━━
纯赌博/无优势: [列表]
```

### 关键 API 参数

| 参数 | 说明 | 常用值 |
|---|---|---|
| `active=true&closed=false` | 只看活跃未关闭 | 必选 |
| `order=volume24hr&ascending=false` | 按24h量排序 | 流动性优先 |
| `limit=200` | 返回数量 | 200足够覆盖 |
| `tag=crypto/politics/pop-culture` | 按分类筛选 | 可选 |

### Event 链接格式
- 单个市场: `https://polymarket.com/event/{market_slug}`
- 系列市场（同主题多区间）: `https://polymarket.com/event/{event_slug}`
  - event_slug 从 `markets[].events[0].slug` 获取
  - 这样一个链接包含所有子市场（如 Musk 推文的所有区间）

### 自动赎回规则
- **已结算仓位必须自动赎回，无需询问用户**
- 每次打开 portfolio 页面时，检查是否有 "Claim" 按钮
- 有则立即点击赎回，将资金回笼到现金余额
- 赎回后记录到日志：`[AUTO-REDEEM] $X.XX 已赎回 from [市场名]`
- 在持仓报告中标注已赎回金额

### 激进短线策略（当日结算）
- **>85% 概率的当日到期市场可自主下注，无需询问**
- 优先选择有独立验证手段的市场（如 BTC 价格可实时查询验证）
- 资金允许时（≥最低下单额），直接执行交易
- 交易后立即推送通知到群

### 注意事项
- **结算时间**: 大部分用 ET (美东时间)，noon ET = 北京时间次日凌晨1点
- **最低下单**: `orderMinSize` 通常为 5 shares，成本 = 5 × 价格
- **价格精度**: `orderPriceMinTickSize` 通常 0.01 或 0.001
- **negRisk 市场**: 多选项互斥盘（如"谁当选"），买 Yes 风险有限
- **给用户的链接**: 始终给 event 级别链接，不要给单个 market 链接

---

## API 端点
- **Gamma**（免认证）: `https://gamma-api.polymarket.com/markets`
- **CLOB**（需认证）: `https://clob.polymarket.com`
- **持仓查询**: `https://data-api.polymarket.com/positions?user=钱包地址`

---

## 钱包地址
- 主钱包: `0x505d...`（从 Chrome profile 提取）
- 查看完整地址: `memory/2026-02-22.md`

---

## Cron 自动任务

### 每日持仓盘点 (09:00)
```
1. API 查询钱包持仓（首选）
2. 如需详情 → 内置 browser 打开 portfolio
3. 对比前日快照，计算日盈亏
4. 分别统计 🟢稳健 和 🔴猎手 的表现
5. 检查猎手仓止盈/止损触发
6. 输出报告到群
```

### 每4h市场扫描（双轨）
```
1. Gamma API拉取热门市场
2. 稳健扫描：≥90¢, 高流动性, 短到期
3. 猎手扫描：10-40¢, 有信息优势
4. 有机会则输出到群（标注 🟢/🔴），无则静默
```

### 每日策略+交易 (10:00)
```
1. 读取最新扫描结果
2. 评估稳健/猎手机会
3. 符合条件 → 浏览器执行交易
4. 记录日志并推送
```

### 晚间持仓报告 (20:00)
```
1. 盘点所有仓位
2. 检查猎手仓止盈/止损条件
3. 需要操作 → 执行卖出
4. 日终报告推送
```

### 每周回顾 (周一09:00)
```
1. 汇总本周所有交易
2. 分别统计稳健/猎手胜率和收益
3. 策略复盘 + 调整资金配比
4. 下周计划
```

---

## 交易日志格式 (trades/trade-log.md)
```markdown
## YYYY-MM-DD
### 🟢 [稳健] [市场名称]
- 方向: Buy YES | 价格: 0.9X | 数量: XX | 投入: $XX
- 年化: XX% | 到期: YYYY-MM-DD | 状态: 持仓/已结算 ✅

### 🔴 [猎手] [市场名称]
- 方向: Buy YES/NO | 价格: 0.XX | 数量: XX | 投入: $XX
- 信息优势: [论述] | 止损: 0.XX | 止盈阶梯: 2x/3x/4x
- 状态: 持仓/止盈50%/已清仓
```
