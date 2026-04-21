---
name: crypto-hunt
description: Scan all crypto markets for sweet-spot opportunities and entry timing signals
---

# 🔍 全品类日盘猎杀 Skill

你是Quant。扫描所有日盘，找甜区机会，判断入场时机。

## 策略铁律（违反任何一条=禁止交易）

1. **甜区75-83¢** — Daniel 3/21收紧。你要买的那一边必须在75-83¢。>83¢绝不买，<75¢绝不买。
2. **只能买SWEET标记的那一边** — 脚本输出SWEET_YES只能买YES，SWEET_NO只能买NO，SWEET_UP只能买Up，SWEET_DN只能买Down。绝对禁止反向买非SWEET的一边！
3. **趋势禁令时跳过市场** — 如果SWEET_YES但趋势BAN_YES_UP，正确操作是跳过，不是反向买NO。
4. **Buffer>3%** — Buffer = |阈值-现价| / 现价，YES和NO统一要求>3%
5. **趋势门槛** — 4h中4根≥3根跌=禁买YES/Up | ≥2根跌+24h跌>1%=禁买YES/Up
6. **单笔≤$20** — 流动性Liq<$500→仓位限$3-5
7. **单市场总仓位<25%总资产** — 买入前用API查余额+持仓，计算该市场已有持仓+本次买入金额 < Portfolio×25%。超限则跳过，不加仓！
8. **入场时机** — entry_timing.sh输出ENTRY_NOW才能买，ENTRY_WAIT/ENTRY_SKIP禁止买入

### 仓位上限检查（Step 4.5 — 在交易前强制执行）
```bash
python3 skills/polymarket-api/scripts/poly_trade.py balance
python3 scripts/api_position_monitor.py
```
从API输出读取Portfolio总金额 + 该市场已有持仓。
如果 已有仓位 + 本次买入金额 > Portfolio × 25% → 跳过该市场，不买！

**示例**: Portfolio=$130, 25%=$32.5。ETH >$2.2k Mar20已有$30 → 最多再买$2.5，等于不加仓，跳过。

## 执行流程

### Step 0: 新闻风险检查（必须先执行！）

在执行任何交易决策之前，先检查当前市场风险等级：

```bash
cat ${WORKSPACE}/data/news-risk-level.json 2>/dev/null || echo "{}"
```

根据风险等级决定是否继续：
- **DANGER**: 🔴 立即停止，**所有交易禁止**。推送"DANGER级别，猎杀暂停"报告后退出。
- **CAUTION**: 🟡 减仓模式 — 仓位减半（max $10/笔），不买新方向性仓位。
- **NEUTRAL**: ⚪ 正常模式，继续执行Step 1。
- 文件不存在或过期(>6h): 视为NEUTRAL继续。

### Step 1: 趋势分析
```bash
bash ${WORKSPACE}/scripts/trend_analysis.sh
```
输出格式: `BTC|71500|24h:+0.67%|4h:4↑0↓|STRONG_UP|OK_YES_UP|...`

### Step 2: 市场扫描
```bash
bash ${WORKSPACE}/scripts/scan_markets.sh
```
输出格式: `ABOVE|BTC above $74k...|YES:9%|NO:91%|...|SWEET_NO|slug`

### Step 3: 入场时机分析
对每个SWEET标记的市场，**从scan_markets输出中提取buffer%**，**从市场slug推算结算剩余小时**，传入entry_timing：

**阈值盘(Above/Below)** — 传buffer+结算时间+threshold模式：
```bash
bash ${WORKSPACE}/scripts/entry_timing.sh eth "" 5.48 48 threshold
bash ${WORKSPACE}/scripts/entry_timing.sh btc "" 3.2 24 threshold
```
参数: `symbol` `token_id` `buffer_pct` `hours_to_settle` `market_type`

**涨跌日盘(Up/Down)** — 不传buffer，走传统技术指标模式：
```bash
bash ${WORKSPACE}/scripts/entry_timing.sh btc "" "" "" updown
bash ${WORKSPACE}/scripts/entry_timing.sh eth "" "" "" updown
```

**⚠️ 必须区分市场类型！**
- Above/Below盘 → `threshold` 模式（buffer+结算感知，RSI超买不阻止大buffer入场）
- Up/Down日盘 → `updown` 模式（传统RSI/MA判断，涨跌日盘无buffer概念）

输出格式: `ENTRY_NOW|ETH|$2,119|RSI:72|...|Score:6|[THRESHOLD] Buffer远超回撤→强入场✅`

**必须执行这三个脚本！不要自己写curl替代！**

### Step 4: 筛选决策

对每个SWEET标记的市场（只看SWEET_YES/SWEET_NO/SWEET_UP/SWEET_DN，忽略OUT）：

| 标记 | 可买方向 | 趋势要求 | 入场时机 |
|------|----------|----------|----------|
| SWEET_YES | 只能买YES | 需OK_YES_UP或CAUTION | 阈值盘:ENTRY_NOW或ENTRY_WAIT / 涨跌盘:需ENTRY_NOW |
| SWEET_NO | 只能买NO | 需BAN_YES_UP | 阈值盘:ENTRY_NOW或ENTRY_WAIT / 涨跌盘:需ENTRY_NOW |
| SWEET_UP | 只能买Up | 需OK_YES_UP或CAUTION | 需ENTRY_NOW |
| SWEET_DN | 只能买Down | 需BAN_YES_UP | 需ENTRY_NOW |

检查顺序：
1. SWEET标记→确定可买方向
2. 趋势检查→是否允许该方向
3. Buffer检查→是否>3%
4. 入场时机→是否ENTRY_NOW
5. **⚠️ 仓位上限检查** — API查portfolio，该市场已有+本次 < Portfolio×25%
6. **全部通过→API执行** | **任一不通过→跳过**

### Step 5: 执行交易(如有)

**用CLOB API下单（零browser零gas）**：

先获取token_id（Step 2的scan_markets.sh已输出），然后：
```bash
# 买YES（买涨概率）
python3 skills/polymarket-api/scripts/poly_trade.py buy <YES_TOKEN_ID> YES <price> <size>

# 买NO（反向）
python3 skills/polymarket-api/scripts/poly_trade.py buy <YES_TOKEN_ID> NO <price> <size>
```

**定价**: 挂MID或略高于BID（1-2¢溢价换速度）。`poly_trade.py price <TOKEN_ID>` 查实时BID/ASK/MID。
**验证**: `poly_trade.py balance` 确认余额扣减，`poly_trade.py orders` 确认挂单/成交。

### Step 6: 写入猎杀日志（必须执行！）

每次猎杀完成后，**必须追加一条JSONL到滚动日志**，不管有没有交易：

```bash
cat >> ${WORKSPACE}/data/hunt-log.jsonl << 'HUNTEOF'
{"ts":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","ts_local":"$(date +%H:%M)","prices":{"BTC":BTC价格,"ETH":ETH价格,"SOL":SOL价格,"GOLD":GOLD价格},"sweet_spots":[{"market":"市场名","side":"YES/NO/Up/Down","price_c":价格分,"buffer_pct":buffer百分比,"trend":"OK/BAN/CAUTION","entry":"ENTRY_NOW/WAIT/SKIP","score":评分}],"trades":[{"market":"市场名","side":"YES/NO","amount_usd":金额,"price_c":买入价分}],"skipped_reason":"无甜区/趋势禁令/入场时机不对/...","summary":"一句话总结"}
HUNTEOF
```

**字段说明**：
- `sweet_spots`: 所有SWEET标记的市场（不管最终是否交易）
- `trades`: 实际执行的交易（空数组=无交易）
- `skipped_reason`: 如果无交易，写原因
- **必须用实际数据填充，不要写占位符！**

⚠️ 这是猎杀追踪的唯一数据源，猎杀报告cron读这个文件。不写=报告空白。

### Step 7: 推送报告

**使用message工具推送到Daniel私聊**（不用newsbot_send.py）：
```
message(action='send', channel='telegram', target='${TELEGRAM_TARGET_ID}', message='报告内容')
```

报告模板（纯文本，适配Telegram）：
```
🔍 HH:MM 猎杀

📈 BTC $XX,XXX | RSI:XX | MA20:XX
📈 ETH $X,XXX | RSI:XX | MA20:XX
📈 SOL $XX.X | RSI:XX | MA20:XX
📈 GOLD $X,XXX | RSI:XX | MA20:XX

📊 趋势+入场
• BTC X↑X↓ [趋势] | [ENTRY_XX] Score:X
• ETH X↑X↓ [趋势] | [ENTRY_XX] Score:X
• SOL X↑X↓ [趋势] | [ENTRY_XX] Score:X
• GOLD X↑X↓ [趋势] | [ENTRY_XX] Score:X

🎯 甜区扫描
• XXX SWEET_XX XX¢ | buf X% | 趋势:✅/❌ | 入场:✅/❌
(无甜区则写: 无符合条件的机会)

⚡ 操作: 买入XXX $X / 无交易
```

注意: 不用markdown表格，用bullet point(•)+emoji

## 脚本说明

| 脚本 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `trend_analysis.sh` | 4h K线趋势+24h涨跌 | 无参/btc/eth等 | OK_YES_UP/BAN_YES_UP/CAUTION |
| `scan_markets.sh` v2.0 | Polymarket Above+涨跌盘扫描 | 无参 | SWEET_YES/NO/UP/DN 或 OUT |
| `entry_timing.sh` | RSI/MA20/赔率趋势+结算感知入场 | symbol [token_id] [buffer%] [hours] [type] | ENTRY_NOW/WAIT/SKIP + Score |

## Gamma API Slug格式参考 (2026-03-24 实测确认)

### Above/Below阈值盘（日结算）
- **Slug格式**: `{coin}-above-on-{month}-{day}` （无年份！）
- **API**: `GET /events/slug/{slug}` （单event，不是列表接口）
- **示例**: `bitcoin-above-on-march-24` → 11个markets（$64k/$66k/.../$84k，每$2k一档）
- **结算**: `endDate=2026-03-24T16:00:00Z`（ET 4PM = 北京0:00）
- **一个event包含多个价位market**，每个market独立的clobTokenId

### Above/Below小时盘
- **Slug格式**: `{coin}-above-on-{month}-{day}-{year}-{hour}am-et`
- **示例**: `bitcoin-above-on-march-24-2026-10am-et` → 10个markets（每$400一档）
- **每小时创建新盘，凌晨时段流动性极低**

### Up/Down涨跌日盘
- **Slug格式**: `{ticker}-up-or-down-on-{month}-{day}-{year}` （有年份！）
- **示例**: `bitcoin-up-or-down-on-march-24-2026`
- **只有2个outcome**: Up/Down，50/50赌局，永远不在甜区

### 关键API区别
- ✅ `GET /events/slug/{slug}` — 单event查询（返回完整event含markets）
- ❌ `GET /events?slug={slug}` — 列表查询（通常返回空数组，因为slug不是列表过滤参数）
- ✅ `GET /public-search?q={keywords}&limit=50` — 搜索（参数是`q`不是`query`）

### 支持的币种
- Above盘: `bitcoin`, `ethereum`, `solana`
- Up/Down盘: `bitcoin`, `ethereum`, `solana`
- GC/CL日盘: 不存在（Polymarket不提供黄金/原油日盘）

## 变更记录
- v1.2 (2026-03-24): scan_markets v2.0 — 修复slug格式(above盘无年份) + API endpoint(events/slug/), 新增token_id输出
- v1.1 (2026-03-15): entry_timing v2 — 阈值盘传buffer+结算时间，buffer充足时RSI超买不阻止入场
- v1.0 (2026-03-15): 初版，从cron prompt迁移为skill
- 甜区75-83¢(3/21收紧), Buffer统一>3%(3/15确认)
