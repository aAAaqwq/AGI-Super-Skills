# 5minbtc — BTC 5 分钟实时方向预测引擎

> 引擎 + LLM 混合架构：量化因子打分基准，LLM 综合裁决，预测 BTC 单根 5 分钟 K 线的方向与收盘价区间。
>
> ⚠️ **NOT FINANCIAL ADVICE / 非投资建议** — 本项目仅为量化研究与学习目的，不构成任何投资、交易或持仓建议。预测存在显著误差，实际交易将面临资金损失风险。详见文末 [免责声明](#免责声明-not-financial-advice)。

[![Engine](https://img.shields.io/badge/engine-v5.7.4-blue)]() [![Python](https://img.shields.io/badge/python-3.8%2B-green)]() [![Deps](https://img.shields.io/badge/dependencies-stdlib%20only-success)]()

---

## 目录

- [核心理念](#核心理念)
- [系统架构](#系统架构)
- [12 正交因子体系](#12-正交因子体系)
- [半 K 线预测策略](#半-k-线预测策略half--candle)
- [黑天鹅三重防护](#黑天鹅三重防护)
- [数据源](#数据源)
- [快速开始](#快速开始)
- [完整运行流程](#完整运行流程)
- [目录结构](#目录结构)
- [回测系统](#回测系统)
- [性能快照](#性能快照)
- [配置说明](#配置说明)
- [已知局限](#已知局限)
- [路线图](#路线图)
- [免责声明](#免责声明-not-financial-advice)
- [License](#license)

---

## 核心理念

5minbtc 解决一个具体问题：**在每根 5 分钟 BTC K 线进行到 ~60–80% 时，预测这根 K 线收盘时的方向和价格区间**。

它不是全自动交易机器人，而是一个 **引擎 + LLM 混合决策系统**：

```
   量化引擎 (12 因子 + ATR 归一化)        LLM (新闻 + 因子 + 裁决规则)
   ┌─────────────────────────┐           ┌──────────────────────────┐
   │ 4 路并行拉取市场数据      │  JSON →  │ 3 路并行新闻搜索          │
   │ 12 正交因子打分           │ ──────→  │ 综合裁决 (可微调引擎结论)  │
   │ Platt Scaling 置信度      │           │ 模板化输出 (15–25 行)      │
   └─────────────────────────┘           └──────────────────────────┘
         纯 Python 标准库                       可由 cron 调度
```

**为什么要混合？** 回测证明：纯价格因子在公平（无前视）条件下无显著预测力（47–49%）。实盘的 edge 主要来自 K 线后段（progress ≥ 0.9）的"已确认走势延续"以及新闻冲击。把数值因子交给 LLM 做上下文综合，比纯规则或纯 LLM 都更稳健。

## 系统架构

### 组件

| 组件 | 文件 | 职责 |
|------|------|------|
| **引擎** | `5minbtc-engine-v5.7.py` | 拉数据 → 计算指标 → 12 因子打分 → 输出预测 JSON（stdout） |
| **新闻** | `5minbtc-news.py` | 抓取 CoinDesk RSS，输出风险等级到 `data/news-risk-level.json` |
| **日志** | `5minbtc-log.py` | 预测记录追加（jsonl）+ 增量 settle（结算上一根 K 线实际结果） |
| **回测** | `backtest/*.py` | 历史数据回测，多版本（v5.6 / v5.7 / v5.8）|
| **LLM** | （外部） | 读引擎 JSON + 新闻，综合裁决并输出 |

### 数据流（单次预测）

```
cron 触发 (每根 5min K线 第4分钟)
   │
   ├─ 5minbtc-log.py settle-all      ← 结算上一根 K 线（写入实际收盘）
   │
   ├─ 5minbtc-engine-v5.7.py         ← 引擎核心
   │     │
   │     ├─ ThreadPoolExecutor(4) 并行:
   │     │    ├─ Binance  Klines   (200 根 5min K线)
   │     │    ├─ Binance  Depth    (订单簿 top-20)
   │     │    ├─ alternative.me FNG (恐惧贪婪指数)
   │     │    └─ Coinbase  BTC-USD  (Chainlink 参考)
   │     │
   │     ├─ 指标: EMA9/21, RSI, MACD, Bollinger, Wilder ATR, Vol-Regime
   │     ├─ 12 正交因子 → score → bias / confidence
   │     ├─ 黑天鹅过滤 (ATR spike / FNG<25 / 新闻熔断)
   │     └─ Chainlink 偏移补偿 (±$300 上限)
   │
   ├─ 5minbtc-news.py                 ← 写 news-risk-level.json
   │
   └─ LLM 读取引擎 JSON + 3 路新闻 → 裁决 → 写日志
```

引擎单次执行约 **~3 秒**（v5.7.3 并行化后，原串行 ~11–18 秒）。

## 12 正交因子体系

v5.0 起用正交因子替代共线指标，所有阈值经 **ATR 归一化**，避免波动率变化导致阈值失效。

| 因子 | 类别 | 含义 |
|------|------|------|
| `momentum` | 趋势 | EMA9−EMA21 差值，ATR 归一化的 t-stat |
| `meanrev` | 均值回归 | 偏离布林带中轨程度 |
| `rsi` | 动量 | Wilder RSI 的 Z-score |
| `volume` | 量能 | 条件化放量信号（区分突破 vs 衰竭）|
| `fatigue` | 衰竭 | 趋势动能衰减检测 |
| `imbalance` | 微结构 | 订单簿买卖盘失衡 |
| `microprice` | 微结构 | Stoikov microprice 偏离 mid |
| `decel` | 衰竭 | 价格变化减速（动量冲突时动态降权）|
| `position` | 位置 | K 线在布林带中的相对位置 |
| `v_reversal` | 反转 | 低点抬高 + 收>开 的 V 型反转模式 |
| `vol_breakout` | 突破 | 最近 3 根完成 K 线的放量突破 |
| **`half_body`** | **半 K 线** | **核心 edge：progress≥45% 时已形成 body 的延续性** |

权重由 `BASE_W` 表给定，并随波动率 Regime（TREND / RANGE / HIGH_VOL / LOW_VOL）动态调整。

## 半 K 线预测策略（Half‑Candle）

这是 v5.7 的核心贡献，也是实盘 edge 的正式建模：

- **S1**：在 K 线进度 ≥ 45% 时激活 `half_body` 因子——已经形成的 body 方向在剩余时间内倾向于延续。
- **S2**：预测范围收窄——ATR 乘数 × 0.55，只预测剩余 ~55% 时间内的波动。
- **S3**：调度时机从每根 K 线第 2 分钟推迟到第 4 分钟（progress ~60–80%），让前半段充分形成信号再预测后半段。

> 实证：回测中 11 因子组合无预测力（47–49%），但实盘 66% 的胜率主要来自 progress=0.9+ 时"确认已有走势"——`half_body` 把这个隐性逻辑变成了显式因子。

## 黑天鹅三重防护（v5.7.1）

引擎在输出预测前进行三层过滤，任一触发即压低置信度或转为 neutral：

1. **ATR Spike 检测**：当前 ATR 相对历史出现尖峰时，方向可靠性下降。
2. **FNG < 25 过滤**：恐惧贪婪指数低于 25（极度恐慌）时标记 `fng_black_swan`。
3. **新闻冲击熔断**：`5minbtc-news.py` 写入 `BLACK_SWAN`/`CRITICAL` 时，引擎强制 bias=neutral、confidence=30。

## 数据源

全部为**公开、免认证**接口，零 API Key：

| 数据 | 来源 | 用途 |
|------|------|------|
| K 线 | `data-api.binance.vision/api/v3/klines` | 200 根 5min OHLCV |
| 订单簿 | `data-api.binance.vision/api/v3/depth` | top-20 bids/asks |
| 恐惧贪婪 | `api.alternative.me/fng/` | 黑天鹅过滤 |
| 参考价 | `api.coinbase.com/v2/prices/BTC-USD/spot` | Chainlink 偏移补偿 |
| 新闻 | `www.coindesk.com/.../rss/` | 风险等级（~14min 延迟）|

## 快速开始

**依赖**：仅 Python 3.8+ 标准库，无需 `pip install` 任何第三方包。

```bash
# 单次运行引擎（输出预测 JSON 到 stdout）
python3 5minbtc-engine-v5.7.py

# 单独跑新闻扫描
python3 5minbtc-news.py

# 结算上一根 K 线 + 追加新预测
python3 5minbtc-log.py settle-all
python3 5minbtc-log.py log "<candle.iso>" <pred_close> <pred_high> <pred_low> \
    <conf> <bias> <news_sent> <vol_pct>
```

引擎输出示例（节选）：

```json
{
  "version": "5.7.3",
  "candle": { "progress_pct": 72.3, "...": "..." },
  "indicators": { "ema9": 61950.1, "rsi": 47.2, "atr": 85.4, "...": "..." },
  "factors": { "half_body": -0.31, "momentum": -0.42, "...": "..." },
  "regime": "TREND",
  "news_risk": "NORMAL",
  "prediction": {
    "bias": "bear", "strength": "moderate",
    "confidence": 48, "pred_close": 61920, "pred_high": 61960, "pred_low": 61870
  }
}
```

## 完整运行流程

完整的"引擎 + LLM"混合流程由 cron 每 5 分钟触发：

```bash
SKILL_DIR=/path/to/5minbtc

# 1. 并行执行：结算 + 引擎 + 新闻
python3 $SKILL_DIR/5minbtc-log.py settle-all
python3 $SKILL_DIR/5minbtc-engine-v5.7.py
python3 $SKILL_DIR/5minbtc-news.py

# 2. LLM 侧：3 路并行新闻搜索
#    - "Bitcoin BTC breaking news price"
#    - "crypto market macro stocks today"
#    - "比特币 BTC 最新 晚间"

# 3. LLM 综合引擎 JSON + 新闻 → 按模板输出（15–25 行）

# 4. 写入预测日志
python3 $SKILL_DIR/5minbtc-log.py log "<candle.iso>" <pred_close> ...
```

> 💡 用 `cp .env.example .env` 并设置 `SKILL_DIR` 指向你的克隆目录，可避免把路径写死。详见 [配置说明](#配置说明)。

## 目录结构

```
5minbtc/
├── 5minbtc-engine-v5.7.py     # 主引擎（cron 调用，输出预测 JSON）
├── 5minbtc-engine-v5.py       # v5 旧版（回测因子模块 import 用）
├── 5minbtc-news.py            # 新闻扫描（CoinDesk RSS）
├── 5minbtc-log.py             # 日志记录 + settle
├── SKILL.md                   # 技能索引文档（Hermes/Claude skill 格式）
├── README.md                  # 本文件
├── .env.example               # 配置模板
├── backtest/
│   ├── fetch_data.py          # Binance 历史数据下载
│   ├── run_backtest.py        # v5.6 回测（公平，因子无预测力）
│   ├── run_backtest_v57.py    # v5.7 回测（含已知前视偏差）
│   ├── run_backtest_v58.py    # v5.8 回测（真实 1min 半 K线，零前视）⭐
│   ├── run.sh                 # 一键运行
│   ├── data/                  # 缓存的 K 线 JSON
│   └── results/               # 回测结果（.gitignore）
├── references/                # 深度文档（架构/教训/pitfalls/黑天鹅…）
├── reviews/                   # 每日复盘报告（按月归档）
├── scripts/                   # 辅助脚本
└── data/                      # 运行时数据（新闻风险等级，.gitignore）
```

## 回测系统

```bash
cd backtest

# 一键回测（下载最新数据 + 运行）
./run.sh

# 快速模式（每小时采样，最近 180 天）
./run.sh --fast

# 最近 90 天，每 6 根 K 线采样
./run.sh --days 90 --sample=6

# 完整因子贡献分析
./run.sh --full-report

# 模拟 K 线进度（progress=0.5 = 中段）
python3 run_backtest.py --progress=0.5
```

**公平性保障**：
- 无前视偏差（当前 K 线价格信息被屏蔽：c=h=l=open, v=0）
- 因子仅基于 200 根已完成 K 线计算
- 回测中订单簿不可获取，imbalance/microprice 设为 0

详见 [`backtest/README.md`](backtest/README.md)。

## 性能快照

> 以下为历史实测数据，**过去表现不代表未来收益**，且小样本下统计显著性有限。

| 版本 | 设定 | 方向准确率 |
|------|------|-----------|
| v4.x | 实盘 | 62.5% |
| v5.7.1 | 实盘 273 轮 | **75.7%** (+13.2pp) |
| v5.8 | 回测（前 2 根 1min） | 61.4% |
| v5.8 | 回测（前 4 根 1min） | 69.5% |

⚠️ 见 [`references/backtest-findings.md`](references/backtest-findings.md)：公平回测下纯价格因子无预测力。实盘高胜率很可能部分来自小样本 + K 线后段信息优势，并非稳定 edge。**在 edge 来源明确前，不应按高胜率预期下注。**

## 配置说明

当前引擎**不读取任何环境变量**——所有参数（symbol、interval、HTTP timeout、ATR 乘数、因子权重）均硬编码在 `.py` 源码中，这保证了 cron 调用的零配置可复现性。

`.env.example` 列出了**建议配置化**的项（当前为预留/文档用途），供希望二次开发的用户参考。如需让引擎实际读取这些变量，需要修改对应源码（欢迎 PR）。

主要硬编码常量位置：

| 常量 | 默认值 | 位置 |
|------|--------|------|
| `symbol` | `BTCUSDT` | `fetch_klines()` / `fetch_depth()` 形参 |
| `interval` | `5m` | `fetch_klines()` 形参 |
| HTTP timeout | `5`–`10` s | `urlopen()` 调用 |
| ATR 乘数 | `0.55` | `predict_close_v5()` |
| `BASE_W` | 因子权重表 | 模块级常量 |
| `REGIME_ADJ` | Regime 权重调整 | 模块级常量 |

## 已知局限

1. **回测与实盘的差距**：公平回测下因子无预测力，实盘 edge 主要来自 K 线后段信息优势（可能不稳定的"半前视"）。
2. **订单簿简化**：仅用 top-20 深度，未实现完整的 OFI（Cont et al. 2014）与 microprice 模型。
3. **新闻延迟**：CoinDesk RSS 约 14 分钟延迟，无法捕捉瞬时冲击。
4. **SSL 验证禁用**：引擎全局设置 `ssl._create_unverified_context`，是为对抗高延迟网络下的 SSL 握手超时（见 `references/high-latency-network-handling.md`）。在可信网络环境下可安全恢复验证。
5. **无自动交易**：本项目只输出预测，不执行任何下单。

## 路线图

详见 [`references/architecture.md`](references/architecture.md)。要点：

- 🔴 **OFI 微结构因子**：接入 Binance WebSocket L2 数据，实现 OFI + microprice（学术 R² 15–25%，5 分钟尺度唯一有实证支持的信号）
- 🟡 HMM Regime 检测 + 自适应仓位
- 🟡 LightGBM 自动化因子筛选
- 🟡 CVaR 动态止损
- 🟢 TFT 多时间尺度模型替代贝叶斯引擎
- 🟢 Deribit 期权 IV 信号

## 免责声明 (NOT FINANCIAL ADVICE)

本项目是**量化研究与教育项目**，不构成投资建议、交易信号或任何形式的财务建议。

- 加密货币市场波动剧烈，交易可能导致**全部本金损失**。
- 引擎预测存在显著误差，历史准确率不代表未来表现。
- 作者与贡献者对任何基于本项目的交易决策**不承担责任**。
- 请在了解当地法律法规的前提下自行承担风险。

如本项目对你有帮助，欢迎 Star。但**请勿**将其视为稳赚的交易工具。

## License

本项目暂未指定开源许可证。如需使用、修改或分发代码，请先联系作者或等待 License 文件添加。在未指定 License 前，根据默认版权法，代码保留全部权利（仅供阅读与学习）。
