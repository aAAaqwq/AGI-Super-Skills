---
name: 5minbtc
version: 5.7.2
description: "BTC 5分钟K线实时方向预测。v5.7.2半K线策略——第2分钟执行(progress~40%)，12正交因子含half_body实体延续+momentum/decel冲突降权+V反转+放量突破+Chainlink价格对齐+Platt Scaling+Bull惩罚。ATR乘数x0.55。黑天鹅防护: ATR spike+FNG<25过滤+新闻冲击熔断。v5.7.2冲突裁决: half_body vs imbalance/microprice(已验证2次实盘)+fatigue≥0.8均值回归预警。Binance端点双向故障切换。"
triggers:
  - 5minbtc
  - 5min btc
  - btc 5min
tools:
  - terminal
  - web
---

# 5minbtc — BTC 5分钟实时预测 v5.7

> 最后更新: 2026-05-28 v5.7 半K线策略

## v5.7 变更 (2026-05-28)

**核心策略变更: 在K线第4分钟执行(progress~80%)，利用前半根K线实体方向确认延续**

设计思路(Daniel提出): 实盘66%准确率的edge来自"确认当前K线已有走势"(progress=0.9+)，v5.7把这个隐性优势显性化。

| 变更项 | 详情 | 效果 |
|--------|------|------|
| S1 `half_body_momentum()` | 新因子，progress≥0.45时激活，ATR归一化实体+tanh压缩 | 将实盘edge显性建模 |
| S2 ATR乘数×0.55 | pred_close乘数 0.20/0.12→0.11/0.066 | 只预测剩余~2.5分钟 |
| S3 half_range缩窄 | 0.65→0.40 | 区间更紧凑 |
| Cron调度 | 第2分钟执行(`2,7,12...`) | progress~40%，前2根1min构建半K线 |
| `BASE_W['half_body']=1.2` | 所有因子中最高权重 | 核心edge因子 |
| `REGIME_ADJ` 更新 | 所有4个regime添加half_body权重 | regime-aware调整 |

`half_body_momentum()` 关键设计:
- 激活阈值: progress≥0.45 (给K线足够时间形成实体)
- 进度加权: `min(1.0, (progress-0.3)/0.7)` — 0.45→0.2, 0.8→0.71, 1.0→1.0
- ATR归一化: body/ATR → tanh(×2.0) → [-1, 1]
- progress<0.45时返回0.0 (不干扰其他因子)

## v5.8 回测方法论突破 (2026-05-28)

**关键改进: 用真实1分钟K线构建半K线状态，零前视偏差**

之前v5.7回测用 `(open+actual_close)/2` 模拟中点→71.2%但含前视偏差；用前一根5min body→48.1%无预测力。
**正确方法(Daniel提出)**: 用对应5min K线的前2-3根真实1分钟K线的OHLCV构建半程状态。

回测结果(半年, 27,237轮方向性):

| 前1根1min (20%) | 前2根 (40%) | 前3根 (60%) | 前4根 (80%) | 前5根 (100%) |
|:---:|:---:|:---:|:---:|:---:|
| 56.7% | **61.4%** | 65.8% | 69.5% | 76.1% |

核心发现:
1. 半K线延续性是真正的alpha来源 — 越接近完成越准，近似线性增长
2. 前2根(当前cron配置): 27,237轮→61.4%, edge +11.4pp, 最长连胜22
3. half_body因子方向准确率仅48.5% — alpha不在因子本身，在于触发了更紧的ATR阈值
4. volume是唯一有独立预测力的因子(56-58%)，其他因子全部49-51%
5. 之前的实盘66%准确率谜团已解开 — 就是半K线延续性效应

回测文件: `backtest/run_backtest_v58.py` (数据: `backtest/data/btcusdt_1m.json`, 259k根)
用法: `python3 run_backtest_v58.py --fast --compare` 或 `--half 3` (前3根1min)

## v5.6 变更 (2026-05-27)

基于3次方向错误深度复盘的4项修复（已实施验证）：

| 修复项 | 变更 | 根因 |
|--------|------|------|
| R1 momentum/decel冲突检测 | \|mom\|>0.7且\|decel\|>0.8且方向相反时，动态降权mom 1.0→0.4, 升权decel 0.7→0.9 | V型反转点momentum锁定错误方向 |
| R2 V型反转因子 | `v_reversal_detect()` 检测低点抬高模式 [-1,1], BASE_W=0.8 | 捕捉结构性的反转信号 |
| R3 放量突破因子 | `vol_breakout_signal()` 用最近3根完整K线的最大量K线方向 [-1,1], BASE_W=0.4 | 避免未完成K线的量价误导 |
| R4 Chainlink价格对齐 | `fetch_chainlink_ref()` Coinbase BTC-USD作参考，自动补偿Binance偏移 | Polymarket结算价≠Binance价格 |

关键代码模式：
- **冲突降权用saved_base模式**: `saved_base = BASE_W.copy()` → 临时改权重 → `combine_factors()` → `BASE_W.update(saved_base)` 恢复。避免跨调用污染全局权重。
- **Chainlink偏移安全边界**: |offset|>300时不补偿（防止API异常导致预测价飞出合理范围）
- **V反转用已完成K线**: 取 `candles[-4:-1]`（最近3根完成K线），不用当前未完成K线
- **输出新增字段**: `chainlink_offset` 追踪每次偏移量, `v_reversal`/`vol_breakout` 因子值

## v5.5 变更 (2026-05-26)

基于120轮v5.4实战复盘的4项优化：

| 优先级 | 修复项 | 变更 | 影响 |
|--------|--------|------|------|
| P0-1 | 置信度校准 | `40+abs(score)` → Platt Scaling sigmoid | conf与准确率正相关 |
| P0-2 | 新闻因子 | 98% NEUTRAL死代码，保留扫描给LLM | 减少噪声 |
| P1-1 | Bull bias | score>0时×0.92衰减 | bear 70.2% > bull 65.4%修正 |
| P1-2 | 高vol惩罚 | HIGH_VOL 0.6→0.45 | 放量准确率更低 |

附加优化：
- neutral区收缩 [-2,2]→[-1,1]，减少无信息预测
- 置信度上限 80→85，让强信号有区分度
- `calibrate_confidence()` 独立函数，midpoint=15, steepness=0.10

## 概述

对当前5min K线做方向判断和收盘预测。架构：**引擎脚本算指标+给基准建议，LLM做综合分析+微调+完整输出**。

## 铁律

1. 每次必须重新执行引擎脚本 — 不缓存
2. 每次必须重新搜索3组新闻
3. 先 settle 上一根，再 log 新预测
4. LLM可微调引擎的bias/pred_close/range，但必须说明理由
5. 输出15-25行（平衡深度和Telegram可读性）

## ⚠️ Pitfalls

### Binance API 端点选择与故障切换

**三层端点策略**（按优先级）：

| 优先级 | 端点 | 场景 | 状态 |
|--------|------|------|------|
| 1 | `api.binance.us` | 通用首选（低延迟网络稳定；2026-06-17间歇超时） | ⚠️ |
| 2 | `data-api.binance.vision` | 备选（低延迟可用，高延迟SSL超时；2026-06-17反向可用） | ⚠️ |
| 3 | `api.binance.com` | 仅供非中国大陆网络 | ❌ 中国大陆451 |

**高延迟网络下的已知问题**：
- 当 ping 8.8.8.8 >250ms 时，`data-api.binance.vision` 的 SSL 握手经常超时（Python `urlopen timeout=10` 不够）
- `api.binance.us` 在此类网络下仍然可用
- **双向故障切换** (2026-06-17): `api.binance.us` 也可能间歇性超时（URLError: timed out），此时 `data-api.binance.vision` 反而可用。两个端点都可能出问题，故障切换必须是双向的——哪个通就用哪个，不要假设某一端总是稳定
- 详见 `references/binance-api-geo.md`

**引擎 + 日志模块端点快速切换**（双向故障切换，两个方向都要支持）：
```bash
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc

# 方向A: 切换到 api.binance.us (当 data-api 不可用时)
sed -i 's|BINANCE_KLINES = .*|BINANCE_KLINES = "https://api.binance.us/api/v3/klines"|' $SKILL_DIR/5minbtc-engine-v5.7.py
sed -i 's|BINANCE_DEPTH = .*|BINANCE_DEPTH = "https://api.binance.us/api/v3/depth"|' $SKILL_DIR/5minbtc-engine-v5.7.py
sed -i 's|data-api.binance.vision|api.binance.us|g' $SKILL_DIR/5minbtc-log.py

# 方向B: 切换到 data-api.binance.vision (当 api.binance.us 不可用时)
sed -i 's|BINANCE_KLINES = .*|BINANCE_KLINES = "https://data-api.binance.vision/api/v3/klines"|' $SKILL_DIR/5minbtc-engine-v5.7.py
sed -i 's|BINANCE_DEPTH = .*|BINANCE_DEPTH = "https://data-api.binance.vision/api/v3/depth"|' $SKILL_DIR/5minbtc-engine-v5.7.py
sed -i 's|api.binance.us|data-api.binance.vision|g' $SKILL_DIR/5minbtc-log.py

# 验证
python3 $SKILL_DIR/5minbtc-log.py settle-all 2>&1 | head -3
```

**验证命令**:
```bash
# 快速测试哪个端点可用
for ep in "api.binance.us" "data-api.binance.vision"; do
  code=$(curl -s --connect-timeout 10 --max-time 15 -o /dev/null -w "%{http_code}" "https://$ep/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=1")
  echo "$ep → HTTP $code"
done
```

### 路径硬编码
不要用 `WORKSPACE = dirname(dirname(dirname(...)))` 指向旧 OpenClaw workspace。用 `SKILL_DIR = os.path.dirname(os.path.abspath(__file__))`。

### 全局字典临时修改模式
当需要临时修改 `BASE_W` / `REGIME_ADJ` 等模块级字典做单次计算时，必须用 saved_base 模式：
```python
saved_base = BASE_W.copy()
BASE_W['momentum'] = 0.4  # 临时修改
raw = combine_factors(factors, regime)
BASE_W.update(saved_base)  # 立即恢复
```
**不要**直接修改后不恢复——Python 模块级字典是全局可变的，下次调用会读到脏数据。

### 🔴 CRITICAL: 回测证明因子无预测力，但半K线延续性有真实edge (2026-05-28更新)

365天105,120根K线回测（`backtest/`目录）揭示的真相：

**v5.6纯价格因子(开盘预测)**:
| 模式 | 当前K线数据 | 方向准确率 | 本质 |
|------|-----------|-----------|------|
| historical_only | 屏蔽 | 47.4% | 低于随机50% |
| fair_live_sim | 屏蔽 | 48.8% | 等于随机 |
| full_lookahead | 含close | 61.1% | 前视偏差 |
| 实盘 (298轮) | progress=0.9+ | 66.1% | 间接前视 |

**v5.8真实1min半K线回测(零前视偏差)**:
| 前2根1min(40%进度) | 前3根(60%) | 前4根(80%) |
|:---:|:---:|:---:|
| **61.4%** (+11.4pp) | 65.8% (+15.8pp) | 69.5% (+19.5pp) |

**结论更新**:
1. 11个技术因子(momentum/RSI/meanrev等)在5分钟尺度上**确实无预测力**(49-51%)
2. volume因子是唯一有独立alpha的(56-58%)
3. **但半K线延续性效应是真实的alpha** — 用真实1min K线构建半K线状态后，准确率61-70%
4. 实盘66%的谜团已解开: 不是前视偏差，是价格动量延续性
5. half_body因子的贡献机制: 不是因子本身有方向预测力(48.5%)，而是它触发了更紧的ATR阈值，让延续性效应更好地转化为预测区间

**回测方法论教训**: 模拟半K线状态时，绝不能用 `(open+actual_close)/2`(前视偏差)或前一根5min body(太粗糙)。必须用对应时间段的**真实1分钟K线**数据。详见 `backtest/run_backtest_v58.py`。

### 🔴 Python 3.11 Unicode Strictness in Engine Source Files

Python 3.11.15 (uv cpython build) rejects **any** non-ASCII character in `.py` files — not just in code, but in **comments and docstrings too**. This includes:
- Full-width punctuation: `，：；（）！？、。` → must use ASCII `,;:()!?.,`
- Math symbols: `≤ ≥ × ÷ ± ★` → `<= >= * / +- *`
- Arrows/dashes: `→ ← ∞ — –` → `> < inf -- -`
- Smart quotes: `' ' " "` → `' "`
- Tilde as "approximately" before decimals: `~2.5` → Python parses `~` as bitwise NOT, giving "invalid decimal literal"
- **Hidden Unicode quotes**: Three `"""` that look correct but contain Unicode left/right double quotes (U+201C/U+201D) instead of ASCII 0x22 — causes "unterminated triple-quoted string"

**Fix strategy** (in order):
1. `sed -i` or Python script for bulk replacements of known character classes
2. Regex: insert space between CJK chars and operators/digits (`CJK+*` → `CJK + *`)
3. If still failing, use `xxd` or `hexdump` to inspect the raw bytes around the error line
4. Nuclear option: strip ALL non-CJK non-ASCII with `content = ''.join(c if ord(c) < 128 or 0x4E00 <= ord(c) <= 0x9FFF else '<REPLACED>' for c in content)`

**Prevention**: When writing Chinese comments/docstrings in engine `.py` files, never mix full-width punctuation or math symbols. Use ASCII punctuation only.

### Cron Job 版本同步
升级引擎后必须同步更新 cron job 的 `name` 字段（如 `"5minbtc v5.6"`）。cron 不自动感知引擎文件版本——它只执行 `5minbtc-engine-v5.py`，文件内容变了 cron 就跑新代码，但 job name 仍是旧标签，导致复盘时混淆实际运行的引擎版本。
**操作**: 每次 engine 升级后，执行 `cronjob(action='update', job_id=..., name='5minbtc vX.Y')`。

## 执行步骤

### Step 1: 并行启动（5个调用同时发出）

```
并行组:
├── exec: settle-all + 引擎脚本 + 新闻扫描（合并一条命令）
├── web_search: "Bitcoin BTC breaking news price" count=3 freshness=day
├── web_search: "crypto market macro stocks today" count=3 freshness=day
└── web_search: "比特币 BTC 最新 晚间" count=3 freshness=day
```

**搜索优化**: 3组通用搜索经常返回首页/目录页而非具体新闻。如果初始结果不具体，立即追加1-2组**上下文定制搜索**：
- 用引擎当前价格方向：`"Bitcoin BTC price [rise/drop/crash] today [当前日期]"`
- 用新闻扫描发现的关键事件：`"BTC [事件关键词] crypto impact [月份] [年份]"`
- 这组搜索在引擎执行后、LLM分析前发起，延迟<30秒但信息价值显著提升

引擎命令（绝对路径）：
```bash
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc && \
  python3 $SKILL_DIR/5minbtc-log.py settle-all 2>&1; \
  echo "---ENGINE---"; \
  python3 $SKILL_DIR/5minbtc-engine-v5.7.py 2>&1; \
  echo "---NEWS---"; \
  python3 $SKILL_DIR/5minbtc-news.py 2>&1
```

新闻扫描会自动更新 `data/news-risk-level.json`（结构化情绪+风险等级），供Step 2使用。

### Step 2: LLM完整分析（参考引擎数据，不是机械填模板）

LLM收到引擎JSON后，必须：

**A. 验收上一根K线**（从settle输出）
- 显示：K线时间、预测 vs 实际、误差、方向✅/❌、区间✅/❌
- 1句偏差复盘

**B. 综合判断方向**（引擎给基准，LLM最终决定）
- 引擎的bias/strength是**参考起点**，不是最终答案
- 读取 `data/news-risk-level.json` 获取结构化新闻情绪
- LLM必须考虑引擎忽略的因素：
  - 超卖/超买后的反转概率
  - BB下轨/上轨的支撑/阻力效应
  - 连续阴/阳线后的疲劳
  - 🔴 **fatigue≥0.8均值回归预警**: 连续下跌/上涨后市场疲劳→反转概率显著升高。即使全因子同向，也必须将confidence上限压至40，并提升反向情景概率至少10pp
  - K线形态（十字星、锤子线、吞没等）
  - 新闻方向的权重调整
- 如果LLM调整了引擎方向，必须说明理由
- **half_body vs imbalance/microprice 冲突裁决 (v5.7.2)**: 当 half_body 与 imbalance/microprice 方向相反时，优先 half_body。原因——imbalance 和 microprice 基于已完成K线的 orderbook 快照（滞后），而 half_body 反映当前半K线的实时价格动量（即时）。实盘验证: 2026-06-04 引擎因 imbalance=-0.82/microprice=-0.82 判 bear weak，但半K线实体+$376 (half_body=+0.35) 是明确 bull 信号——实盘收涨✅；2026-06-17 引擎因 imbalance=+0.99/microprice=+0.99 判 bull weak，但半K线实体-$82 (half_body=-0.41) + MACD转负 是明确 bear 信号——实盘收跌✅。两次验证均证明: 已完成K线的 orderbook 因子在K线初段是滞后指标，半K线实时动量是即时指标。裁决条件: |half_body|>0.25 且 |imbalance|>0.5 且方向冲突时触发

**C. 微调预测价**（引擎给基准，LLM微调±ATR*0.3以内）
- 引擎pred_close是数学基准
- LLM可基于K线形态、新闻、超卖反弹等调整
- 调整幅度不超过ATR*0.3

**D. 完整输出**（包含技术分析逻辑，不是只列数字）

### Step 3: 记录日志

```bash
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc && \
  python3 $SKILL_DIR/5minbtc-log.py log \
  "<engine.candle.iso>" \
  <final_pred_close> \
  <final_pred_high> \
  <final_pred_low> \
  <confidence> \
  <final_bias> \
  <news_sentiment> \
  <engine.indicators.vol_pct>
```

## 输出模板

```
✅ 验收: [上次K线时间] pred=$XX,XXX actual=$XX,XXX err=±$XX (±X.XX%) dir✅/❌ rng✅/❌
[1句复盘]

📈 BTC 5min 实时预测 @ HH:MM:SS
当前K线: HH:MM→HH:MM | ⏱ XX.X% (剩XmXs)
实时价: $XX,XXX | O=XX,XXX H=XX,XXX L=XX,XXX C=XX,XXX (body ±$XX)
---
📰 今日关键新闻 [结构化信号: 🟢BULLISH/🟡NEUTRAL/🔴BEARISH | 风险: LOW_RISK/NORMAL/ELEVATED/HIGH_VOL]:
- 🟢 [新闻1] — 影响
- 🟡 [新闻2] — 影响
- 🔴 [新闻3] — 影响
新闻净效应: 🟢/🟡/🔴 [原因] | 结构化: [news-risk-level.json sentiment]

🧭 方向: 📈/📉 [bull/bear] [strong/medium/weak] | 依据: [2-3个关键指标+新闻]
- 引擎基准: [engine bias/strength] → LLM调整: [如有调整写理由，无则写"确认引擎判断"]
- EMA9=$XX,XXX / EMA21=$XX,XXX (Δ±$XX)
- RSI=XX.X [超买/超卖/中性]
- MACD=XX.X / Signal=XX.X (Hist=XX.X)
- BB: $XX,XXX / $XX,XXX / $XX,XXX [价格位置]
- ATR=$XX.X | Vol=XX% of avg [放量/缩量/正常]

[2-3句核心分析：结合技术+新闻+K线形态的综合判断]

---
🎯 收盘预测:
| 情景 | 目标区间 | 概率 |
|------|---------|------|
| [主要情景] | $XX,XXX-$XX,XXX | XX% ← |
| [次要情景] | $XX,XXX-$XX,XXX | XX% |

**开盘$XX,XXX → 预测$XX,XXX** (±$XX, ±X.XX%) → 📈/📉

> [1句关键备注]
```

## 引擎JSON结构（LLM直接读取）

v5.6输出示例（实际字段名）：
```json
{
  "version": "5.6",
  "candle": {"now":"22:10:26","candle_start":"22:10","candle_end":"22:15","progress_pct":8.9,"remaining_sec":273,"iso":"..."},
  "price": {"current":74978.01,"open":75020.0,"high":75037.42,"low":74950.64,"body":-42,"body_pct":-0.056},
  "recent_candles": [{"O":75000,"H":75102,"L":74928,"C":75073}, ...],
  "indicators": {
    "ema9":75099.4, "ema21":75298.7, "ema_delta":-199.3,
    "rsi":32.5, "macd":-209.78, "macd_signal":-191.92, "macd_hist":-17.86,
    "bb_upper":76060.4, "bb_mid":75357.1, "bb_lower":74653.9,
    "atr":155.6, "vol_pct":19.0
  },
  "fng": {"value":25, "label":"Extreme Fear"},
  "factors": {
    "momentum": -0.968, "meanrev": 0.431, "rsi": -0.351,
    "volume": 0.25, "fatigue": 0, "imbalance": 0.234,
    "microprice": 0.246, "decel": 1.0, "position": 0.798,
    "v_reversal": 0, "vol_breakout": 0
  },
  "regime": "TREND",
  "chainlink_offset": -152,
  "prediction": {"bias":"bull","strength":"weak","confidence":45,"score":1,
                 "pred_close":74860,"pred_high":74954,"pred_low":74766}
}
```

**v5.6新增字段说明**:
- `chainlink_offset`: Binance→Chainlink价格偏移（$），已自动补偿pred_close/high/low。LLM在输出末尾注明此偏移即可
- `fng`: Fear & Greed Index，值为null时API不可用
- `factors.v_reversal`: V型反转因子 [-1,1]，0=无反转信号
- `factors.vol_breakout`: 放量突破因子 [-1,1]，0=无突破信号
- `atr_spike`: ATR异常检测 {detected, ratio, consecutive} — v5.7.1 P0-1
- `fng_black_swan`: bool — v5.7.1 P0-2: FNG<25时为True
- `news_risk`: str — v5.7.1 P0-3: "NORMAL"/"BLACK_SWAN"/"CRITICAL"
- `black_swan_warning`: str|null — v5.7.1 P0-3: 黑天鹅警告信息
- `price.body_pct`: body百分比，正=阳线，负=阴线
```

## 复盘

```bash
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc && \
  python3 $SKILL_DIR/5minbtc-log.py stats
```

## 新闻数据源

| 源 | 延迟 | 状态 |
|-----|------|------|
| **CoinDesk** | **~14min** | ✅ RSS实时 |
| **Cointelegraph** | **~3min** | ⚠️ 需TG脚本（已降级为RSS fallback） |
| **TreeNews** | ~120min | ⚠️ 需TG脚本（已降级） |

## 版本演进

| 版本 | 架构 | 方向准确率 | 关键变更 |
|------|------|-----------|----------|
| v3.1 | 线性打分(EMA+RSI+MACD+Vol) | 64% | 基础版，引擎+LLM混合 |
| v3.5.1 | +低vol衰减/VWAP因子 | 77% | 最佳版本 |
| v4.0 | Hermes迁移 | 60.5% | 路径适配，功能不变 |
| v4.1 | Phase1修复 | 目标70%+ | 过度自信压制+放量反转+bull修正+疲劳增强 |
| v5.4 | 正交因子+Regime | 68.1%(120r) | 9正交因子+sigmoid+TREND dampening+meanrev反转 |
| **v5.5** | **+校准置信度** | **71.4%(28r)** | **Platt Scaling+Bull惩罚+高vol增强+neutral区收缩** |
| **v5.6** | **+冲突检测+V反转+Chainlink** | **66.1%(298r实盘) / 47.4%(105k回测)** | **mom/decel冲突降权+V反转因子+放量突破+Coinbase价格对齐。⚠️ 实盘edge来自前视偏差(progress=0.9+)，公平回测无预测力** |
| v5.7 | **半K线策略+half_body因子** | **61.4%回测(前2min) / 69.5%(前4min)** | **第2分钟执行+half_body_momentum因子(BASE_W=1.2)+ATR×0.55+half_range 0.40。v5.8回测用真实1min K线证实半K线延续性有真实edge(+11.4~+19.5pp)** |
| **v5.7.1** | **+黑天鹅防护** | **72.0% (100r实盘) / 61.4%回测(V8)** | **P0-1: ATR spike检测(1.5x阈值+连续3根→regime强制HIGH_VOL+conf减半) / P0-2: FNG<25极端恐惧过滤(v_reversal×0.5+decel×0.7) / P0-3: news_risk circuit breaker(BLACK_SWAN/CRITICAL→neutral+conf=30)。2026-05-28美伊空袭复盘驱动。6月实盘100轮方向83.0%: 06-03=79.2%(24r) → 06-06=90.9%(33r)🏆 → 06-09=88.9%(18r) → 06-12=68.0%(25r) 缩量(≤80% vol)方向≥95% ✅** |
| **v5.7.2** | **+imbalance冲突裁决+fatigue预警** | **2/2裁决验证✅** | **half_body vs imbalance/microprice冲突裁决规则: |half_body|>0.25且|imbalance|>0.5时优先实时半K线动量。2026-06-04(半K线bull翻engine bear✅)+2026-06-17(半K线bear翻engine bull✅)两次实盘验证。fatigue≥0.8均值回归预警: conf上限40+反向+10pp。Binance端点双向故障切换。** |

> ⚠️ **回测警示(2026-05-28更新)**: v5.6纯价格因子在开盘预测时准确率仅47-49%。但v5.8用真实1min K线构建半K线后，准确率61.4%(前2根)~69.5%(前4根)，证实半K线延续性有真实edge。half_body因子本身无方向预测力(48.5%)，其贡献在于触发更紧ATR阈值。详见 `references/backtest-findings.md` 和 `backtest/run_backtest_v58.py`。

### 全量复盘 (273笔结算, 截至2026-05-27)

| 日期 | 引擎 | 笔数 | 方向 | 区间 | 行情特征 |
|------|------|------|------|------|----------|
| 05-05 | v4.x | 107 | 64.5% | 55.1% | 震荡+突破 |
| 05-06 | v4.x | 28 | 57.1% | 71.4% | 横盘 |
| 05-11 | v4.x | 12 | 66.7% | 91.7% | 小样本 |
| 05-12 | v4.x | 5 | 40.0% | 60.0% | 小样本最差 |
| 05-23 | v5.4 | 37 | 64.9% | 73.0% | v5.4首日 |
| 05-24 | v5.4 | 30 | 73.3% | 76.7% | -1.09%单边下跌🏆 |
| 05-25 | v5.4 | 26 | 61.5% | 88.5% | +0.43%震荡 |
| 05-27 | v5.5 | 28 | 71.4% | 75.0% | -0.78%震荡下跌 |
| 06-03 | v5.7.1 | 24 | **79.2%** | 54.2% | -6.9%单边下跌, FNG=11 |
| 06-06 | v5.7.1 | 33 | **90.9%** 🏆 | 78.8% | 缩量震荡, FNG=12~14 |
| 06-09 | v5.7.1 | 18 | **88.9%** | 61.1% | 16连胜, 缩量≤80%方向100% |
| 06-12 | v5.7.1 | 25 | **68.0%** | 40.0% | bear中量区44.4%溃败 |
| 06-14 | v5.7.1 | 32 | **65.6%** | 53.1% | bear弱反弹盲区57.9%, 10连胜开局 |

**引擎迭代对比**:
- v4.x (152轮): 方向 62.5% | Range 61.2%
- v5.4 (93轮): 方向 66.7% | Range 78.5%
- v5.5 (28轮): 方向 71.4% | Range 75.0%
- v5.7.1 (100轮): 方向 83.0% (06-03: 79.2%, 06-06: 90.9%🏆, 06-09: 88.9%, 06-12: 68.0%, 06-14: 65.6%)
- v5.x合计 (221轮): 方向 77.8% (+15.3pp vs v4)

### 核心教训

1. **🔴 纯价格因子无预测力，但半K线延续性有真实edge** — 11因子全部49-51%，但用真实1min K线构建半K线后准确率61-70%。edge来自价格动量延续，不是技术指标。回测时必须用真实1min数据，不能用模拟中点
2. **半K线延续性是可利用的真实效应** — v5.8回测(27k轮)证实: 前2根1min=61.4%, 前4根=69.5%。越接近K线完成越准。实盘66%准确率已解释
3. **过度自信是最致命问题** — conf≥60准确率56.8% < conf<60的65.4%，极端信号=行情末端
4. **放量≠确认方向，放量=反转预警** — 放量(≥80%)准确率仅50%
5. **bull偏向严重** — bull准确率57.3% < bear 63.4%，引擎过度解读EMA金叉
6. **线性打分是初学者错误** — 多个共线指标叠加不增加信息量
7. **🔴 缩量场景(<50% vol) = 半K线策略最强edge — 2026-06-03实盘7/7 100%准确率** — 缩量意味着没有突发因素干扰半K线延续性，half_body因子在低vol市场中被锁定。这从v5.4时代"低vol微波动准确率最高"(66%)的观察，升级为半K线策略的核心优势。v5.8回测中volume因子是唯一有独立预测力的因子(56-58%)，与实盘互为印证。**这条经验来自2026-06-03实盘复盘**。
8. **EMA在底部反弹期天然滞后** — VWAP因子部分修复
9. **momentum/decel冲突时，decel通常是正确的** — 当 |momentum_tstat|>0.7 且 |decel|>0.8 且方向相反时，长期斜率锁定错误方向，短期反转才是真相（V型反转场景）
10. **volume因子使用未完成K线判断方向是致命缺陷** — 预测时点candle仅完成60-70%，应改为用最近3根完整K线的量价关系
11. **bear方向在中量区(40-80%)是v5.7.1最大盲区 (2026-06-12)** — 缩量场景(<40%)和bull方向表现优异(87-100%)，但bear中量区准确率仅44.4%(低于随机)。趋势市场中的区间震荡导致半K线延续性失效。**修复方向**: bear中量区需增加额外确认规则(如连续2根同向半K线才出方向)
    - **变体: 持续下跌后的弱反弹是bear方向另一盲区 (2026-06-14)**: 32轮方向65.6%，bear仅57.9%(11/19)。8次bear误判全部是"预测跌但实际涨" — 持续下跌后BTC出现弱反弹时，半K线延续性错误地将反弹视为继续下跌。21:00-22:00区间6次bear全部打脸。根因: 下跌半K线延续性过强，无法区分"延续下跌"vs"震荡筑底反弹"。**修复方向**: 连续3根以上bear完成K线+当前半K线收涨时，bear需降权或升至中立
12. **imbalance/microprice 因子滞后于半K线实时动量 (v5.7.2)** — 当当前半K线实体方向与 imbalance/microprice 冲突时，已完成K线的 orderbook 因子是滞后指标，半K线实时动量是即时指标。裁决: |half_body|>0.25 且 |imbalance|>0.5 时优先 half_body。2026-06-04 实盘: 引擎判 bear(imbalance=-0.82)，但半K线 bull 实体+$376 正确
13. **周末低流动性放大误差 (2026-06-14)**: 周日(06-14)的MAE=0.045%与平日相当，但22:35出现了-0.22%的极端误差（pred=$64,020 actual=$63,880）。周末BTC波动率降低但偶发性价差放大，建议周末自行降低ATR乘数或减少预测频率
14. **🔴 fatigue≥0.8 = 均值回归预警 (2026-06-17)**: 22:40 candle — 全因子bear共振(momentum=-0.85/imbalance=-0.73/MACD hist=-26.6/vol=3%)，LLM判bear medium，但实际收涨(+$87)。根因: fatigue=0.8表示连续下跌后市场疲劳，缩量环境下的均值回归概率显著升高。**裁决规则**: fatigue≥0.8时，即使全因子同向，也需将置信度上限压至40，并提升反向情景概率至少10pp。fatigue=0.8是本轮唯一反向信号，却被忽略，导致方向误判。**与06-14 bear弱反弹盲区(教训11)的关联**: 两者都是\"连续下跌后的反弹\"模式——06-14是半K线延续性过强无法区分筑底，06-17是fatigue信号被全因子压制。共同修复方向: 连续下跌≥3根K线后，需增加反弹确认机制

### 2026-06-03 复盘新增经验

**v5.7.1首日实盘(6月3日)**: 24轮已结算，方向准确率79.2%(19/24)，区间54.2%(13/24)，MAE 0.106%。详见 `review-2026-06-03.md`。

**5个方向误判的根因模式**:
| 时间 | 引擎方向 | 实际方向 | 误差 | vol | 根因模式 |
|------|---------|---------|-----|-----|---------|
| 20:04 | bear | +0.30% | ❌❌ | 163% | 巨量开盘+冲突降权未完全覆盖 |
| 20:37 | bear | +0.21% | ❌❌ | 83% | 开仓延迟: 20:36 bull→20:37 bear转多 |
| 20:54 | bear | +0.16% | ❌❌ | 34% | 纯噪声区间: 缩量反向锁死 |
| 20:57 | bull | -0.06% | ❌❌ | 37% | 量价背离: 缩量bear bull锁死 |
| 21:06 | bull | -0.08% | ❌❌ | 81% | Pattern A: momentum 15-candle OLS滞后 |
| 21:28 | bull | -0.01% | ❌❌ | 156% | 缩量变放量+开仓末期反转 |

**缩量场景(<50% vol)表现**: 7/7方向100%准确率 — 半K线策略的核心优势区域。
**FNG=11极端恐惧下表现**: 黑天鹅防护正常激活，v_reversal×0.5+decel×0.7，但ATR正常+news=NORMAL未触发熔断 — 设计合理。

## v5.0 升级路线图

> 详见 `references/quant-knowledge-index.md` 和 `~/.hermes/profiles/cqo/quant-knowledge/R12-integration-blueprint.md`

### v5.6 方向错误修复（✅ 已实施 2026-05-27）

基于2026-05-27深度复盘的3次方向错误分析，已全部落地到引擎代码：

| 优先级 | 修复项 | 状态 | 实现 |
|--------|--------|------|------|
| R0 | momentum/decel冲突检测 | ✅ `direction_rule_v5()` | saved_base模式动态降权mom→0.4, decel→0.9 |
| R1 | V型反转因子 | ✅ `v_reversal_detect()` | BASE_W=0.8, TREND/HIGH_VOL下加权至0.9/1.0 |
| R2 | 放量突破因子 | ✅ `vol_breakout_signal()` | 用最近3根完成K线，BASE_W=0.4 |
| R3 | Chainlink价格对齐 | ✅ `fetch_chainlink_ref()+run()` | Coinbase BTC-USD参考，偏移补偿上限±$300 |

**案例复盘要点**：
- 20:20巨量突破(vol=182%)：decel=+1.0正确预判反转，但mom=-0.98权重×1.0淹没反转信号 → **R0冲突检测修复**
- 20:25放量延续(vol=123%)：同上，momentum仍在消化15根K线的下跌斜率 → **R0冲突检测修复**
- 20:50低vol(vol=33%)：RANGE regime下meanrev权重放大推高bull，实际仅$2波动 → **v5.5 neutral区收缩已覆盖**

**实时验证**: 22:09 CST 运行恰好命中冲突场景(mom=-0.981, decel=+1.0)，输出bear conf=45% score=-1

### P0 — 立即实施（回测验证后的修订优先级）
1. **🔴 OFI微结构因子是唯一出路** — 回测证明纯价格因子无预测力。必须接入Binance WebSocket获取orderbook L2数据，实现OFI(Cont et al. 2014)和Stoikov microprice。学术文献R²=15-25%，是5分钟尺度唯一有实证支持的信号
2. **新闻脉冲信号** — 突发事件(Big发布/SEC/ETF)可在5分钟内产生方向性冲击，作为互补信号
3. **降低实盘仓位** — 在edge来源明确前，不应按66%胜率预期下注。实盘66%大概率是小样本+前视偏差的假象

### P1 — 2-4周
4. Regime-aware仓位 (HMM检测)
5. LightGBM自动化因子筛选
6. CVaR动态止损

### P2 — 1-2月
7. TFT多时间尺度模型 → 替代贝叶斯引擎
8. 期权IV信号 (Deribit)
9. 完整压力测试框架

### 关键数学升级
- OFI (Cont et al. 2014) → 替代纯价格指标
- Microprice (Stoikov 2018) → 替代 mid price
- Kalman滤波 → 动态EMA权重
- HMM Regime → 自适应仓位
- GPD尾部 → 替代固定止损

## 参考文件

- `references/binance-api-geo.md` — Binance API 区域封禁解决方案和迁移记录
- `references/quant-knowledge-index.md` — 50轮蒸馏知识库索引(14份报告/~80KB)，含升级优先级
- `references/polymarket-data-source.md` — Polymarket BTC价格结算源(Chainlink Data Streams)、与Binance价差分析、对预测引擎的影响
- `references/performance-history.md` — 全量实战记录(273轮/8天)，按日详细数据+引擎迭代对比+3大错误模式归因
- `references/backtest-findings.md` — 365天回测深度复盘：因子无预测力证据、前视偏差诊断、A/B三种模式对比、战略建议
- `references/session-2026-06-17.md` — 2026-06-17 5轮实时预测: v5.7.2冲突裁决再验证(2/2)✅、fatigue≥0.8误判分析、Binance端点双向故障切换
- `references/dreaming-cron-recovery.md` — Dreaming Cron故障恢复指南: 数据源不可用恢复步骤、验证命令、配置参考
- `references/backtest-v58-1min-findings.md` — v5.8真实1min半K线回测：零前视偏差方法论、前2根1min=61.4%准确率、因子贡献分析、半K线延续性alpha证据

## 复盘记录文件

存放在 skill 目录根下，按日期命名：
- `review-2026-05-24.md` — v5.4 单边下跌日复盘（方向73.3%）
- `review-2026-05-25.md` — v5.4 震荡市复盘（Range 88.5%历史最佳，方向61.5%）
- `review-2026-05-27.md` — v5.6 3次方向错误深度复盘 + 4项修复实施 + 8天273轮总战绩
- `review-2026-06-03.md` — v5.7.1 首日24轮实盘复盘（方向79.2%, 缩量100%, 5个误判模式分析）
- `backtest/review-backtest-2026-05-27.md` — 365天回测深度复盘 + 因子无预测力证据 + 前视偏差诊断

## 报告库

14份深度蒸馏报告存放在 `reports/` 目录（也同步在 AGI-Super-Team 仓库）：
- R01-R12：50轮蒸馏（因子理论、策略、DeFi、组合、ML、数据源、前沿研究、期权、微结构、风控、机构方法论、整合蓝图）
- R13：准确率优化方案（178笔复盘后）
- R14：引擎审计报告（顶尖量化审查，4个Critical修复→v5.0架构设计基础）

## 仓库同步

Skill已同步至 AGI-Super-Team 仓库 `skills/5minbtc/`。

```bash
# 1. rsync 本地最新版到共享仓库（排除运行时数据和日志）
rsync -av \
  --exclude='data/' --exclude='__pycache__/' \
  --exclude='*.jsonl' --exclude='*.jsonl.*' --exclude='*.gz' \
  /home/aa/.hermes/profiles/cqo/skills/5minbtc/ \
  /home/aa/clawd/repos/AGI-Super-Team/skills/5minbtc/

# 2. 提交推送
cd /home/aa/clawd/repos/AGI-Super-Team
git add skills/5minbtc/
git commit -m "sync(skills/5minbtc): <变更简述>"
git push origin master
```

**Commit message 惯例**: `sync(skills/5minbtc): <版本> 全量同步 — 引擎+回测+复盘+参考文档`

**同步内容**:
- ✅ 引擎 (`5minbtc-engine*.py`)、日志模块 (`5minbtc-log.py`)、新闻模块 (`5minbtc-news.py`)
- ✅ `SKILL.md`（含冲突裁决规则同步）
- ✅ `backtest/`（含脚本、结果JSON、README）
- ✅ `references/`（含黑天鹅防御、Dreaming恢复、Binance地理、性能历史）
- ✅ `review-*.md` 全量复盘记录
- ❌ `data/`、`__pycache__/`（运行时产物）
- ❌ `*.jsonl`、`*.jsonl.*.gz`（海量预测日志，按需同步）

**同步前dry-run验证**:
```bash
rsync -av --dry-run \
  --exclude='data/' --exclude='__pycache__/' --exclude='*.jsonl' --exclude='*.jsonl.*' --exclude='*.gz' \
  /home/aa/.hermes/profiles/cqo/skills/5minbtc/ \
  /home/aa/clawd/repos/AGI-Super-Team/skills/5minbtc/
```

**推送前检查point**: 确保不包含敏感数据（密钥、API凭证）、市场数据（data/）、海量日志（*.jsonl.gz）

## 回测系统

```
backtest/
├── fetch_data.py            # Binance历史数据下载器(分页+断点续传)
├── run_backtest.py          # v5.6回测引擎(导入v5.6因子模块, A/B三种模式)
├── run_backtest_v57.py      # v5.7回测(用模拟半K线，已证实有前视偏差问题)
├── run_backtest_v58.py      # v5.8回测(用真实1min K线构建半K线，零前视偏差) ← 推荐使用
├── run.sh                   # 一键运行(--fast/--sample/--days/--skip-fetch)
├── README.md                # 使用文档
├── data/
│   ├── btcusdt_5m.json      # 5分钟K线数据(105k根, 12MB)
│   └── btcusdt_1m.json      # 1分钟K线数据(259k根, 29MB) — v5.8回测用
└── results/                 # 回测结果(gitignore)
```

运行命令:
- `cd backtest && python3 run_backtest_v58.py --fast --compare` — v5.8快速回测(推荐)
- `cd backtest && python3 run_backtest_v58.py --half 3` — 用前3根1min
- `cd backtest && python3 run_backtest_v58.py --days 180 --full-report` — 完整半年报告
