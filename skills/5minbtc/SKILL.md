# 5minbtc — BTC 5分钟实时预测 v5.7.4

> BTC 单根 5min K线 方向 + 收盘价预测。引擎+LLM 混合架构。
> **SKILL.md 是索引, 详细内容见 `references/`。**

## 触发
`5minbtc` / `5min btc` / `btc 5min`

## 何时使用
| 场景 | 做法 |
|------|------|
| 当前 5min K线 方向+价位 | ✅ 标准流程, 有真实 edge (v5.8 回测 61-70%) |
| "今晚 BTC 涨跌" (宽窗口) | ⚠️ 跑当前 K线 + 给方向倾向, 标注"超出引擎置信区间" |
| "下根 K线" / "1小时后" | 引导在该 K线 起始时间再触发 |

## 快速开始

```bash
SKILL_DIR=/home/aa/.hermes/profiles/cqo/skills/5minbtc

# 1. 并行: 引擎 + 新闻 + settle (前一根)
python3 $SKILL_DIR/5minbtc-log.py settle-all 2>&1
python3 $SKILL_DIR/5minbtc-engine-v5.7.py 2>&1
python3 $SKILL_DIR/5minbtc-news.py 2>&1

# 2. 3 路 web_search (并行)
# "Bitcoin BTC breaking news price" / "crypto market macro stocks today" / "比特币 BTC 最新 晚间"

# 3. LLM 分析 → 输出 (见 output-template.md)
# 4. 写日志
python3 $SKILL_DIR/5minbtc-log.py log \
  "<candle.iso>" <pred_close> <pred_high> <pred_low> \
  <conf> <bias> <news_sent> <vol_pct>
```

## 架构 (1 行/组件)
- **引擎** `5minbtc-engine-v5.7.py`: 12 正交因子 + 半 K线策略 + 4路并行 HTTP (~3s)
- **日志** `5minbtc-log.py`: jsonl 追加 + 增量 settle
- **新闻** `5minbtc-news.py`: CoinDesk RSS (唯一稳定源, ~14min 延迟)
- **LLM**: 因子打分基准 + LLM 综合裁决 + 模板输出

## 铁律
1. 每次必须重新执行引擎脚本 — 不缓存
2. 每次必须重新搜索3组新闻
3. 先 settle 上一根, 再 log 新预测
4. LLM 可微调引擎的 bias/pred_close/range, 但必须说明理由
5. 输出 15-25 行 (平衡深度和 Telegram 可读性)

## 关键裁决规则 (LLM 决策时必查, 详见 output-template.md)
- **half_body vs imbalance 冲突** (v5.7.2): |half_body|>0.25 + |imbalance|>0.5 + progress≥45% → 优先 half_body
- **TREND 强趋势 decel 约束** (v5.7.4): EMA delta>$100 时 |decel|>0.7 需 |half_body|>0.15 同向确认
- **fatigue≥0.8**: conf 上限 40, 反向 +10pp
- **chainlink_offset 矛盾**: bias=bull 但 pred_close<current → 以 current 为锚 ±ATR×0.3
- **极端进度 (>80%)**: pred_close 按剩余时间比例缩放
- **Body=0 持续模式**: pred_close → current ± ATR×0.2, conf 降至 35-42%

## 性能快照 (2026-07-05)
- v5.7.1 实盘 273 轮方向 75.7% (v4.x 62.5%, +13.2pp)
- v5.8 回测: 前2根 1min=61.4%, 前4根=69.5% (半 K线延续性)
- 当前 cron: `zai/glm-5.2` (8-15s/次) | opencaio 实测 MiniMax-M3 ~2.7s 可作更快选项

## 📚 引用索引 (references/)

### 核心方法论
- [lessons.md](references/lessons.md) — **22 条核心教训** (必读)
- [pitfalls.md](references/pitfalls.md) — **22 条 pitfalls 集中索引** (必读)
- [changelog.md](references/changelog.md) — v5.0 ~ v5.7.4 详细变更
- [architecture.md](references/architecture.md) — 引擎架构 + 因子模型 + v5.0 升级路线图

### 执行与输出
- [execution.md](references/execution.md) — 完整执行步骤 + 铁律 + 宽窗口处理
- [output-template.md](references/output-template.md) — LLM 输出模板 + 裁决规则

### 数据源 & 网络
- [news-sources.md](references/news-sources.md) — 新闻源评估 (清理后只剩 CoinDesk)
- [binance-api-geo.md](references/binance-api-geo.md) — Binance 端点区域问题
- [binance-endpoint-flapping.md](references/binance-endpoint-flapping.md) — 端点双向故障切换
- [high-latency-network-handling.md](references/high-latency-network-handling.md) — 高延迟网络处理 (SSL 超时)
- [polymarket-data-source.md](references/polymarket-data-source.md) — Polymarket 结算源 (Chainlink)

### 引擎专项
- [engine-parallelization-v573.md](references/engine-parallelization-v573.md) — v5.7.3 HTTP 并行化 + positional arg 陷阱
- [black-swan-defense-v571.md](references/black-swan-defense-v571.md) — v5.7.1 黑天鹅防护 (ATR+FNG+news)
- [decel-collapse-pattern.md](references/decel-collapse-pattern.md) — decel 极值崩塌 = V反完成
- [cron-llm-provider-failure.md](references/cron-llm-provider-failure.md) — Cron LLM Provider 失效诊断
- [cron-setup.md](references/cron-setup.md) — Cron Job 配置 + 版本同步
- [dreaming-cron-recovery.md](references/dreaming-cron-recovery.md) — Dreaming Cron 恢复

### 回测 & 复盘
- [backtest-findings.md](references/backtest-findings.md) — 365 天回测深度复盘 + 因子无预测力
- [backtest-v58-1min-findings.md](references/backtest-v58-1min-findings.md) — v5.8 真实 1min 半 K线回测
- [review-procedure.md](references/review-procedure.md) — 每日复盘流程 + 数据质量检查
- [performance-history.md](references/performance-history.md) — 273 笔全量战绩 + 引擎迭代对比

### 单次 session 记录
- [session-2026-06-17.md](references/session-2026-06-17.md) — 5 轮实时预测, v5.7.2 验证
- [session-2026-06-18.md](references/session-2026-06-18.md) — 00:10 mispredict 复盘 → v5.7.4 规则

### 数据采集 & 仓库
- [daily-stock-analysis-data-sources.md](references/daily-stock-analysis-data-sources.md) — daily_stock_analysis 17-fetcher 评估
- [sync-procedure.md](references/sync-procedure.md) — AGI-Super-Team 同步流程
- [quant-knowledge-index.md](references/quant-knowledge-index.md) — 50 轮蒸馏知识库索引

## 复盘记录 (`reviews/`)
按月归档:
```
reviews/
├── 2026-05/  (6 份: review-2026-05-05.md, 24, 25, 27, 27-backtest, 29)
├── 2026-06/  (15 份: 03, 06, 09, 12, 14, 15, 16, 17, 18, 19, 21, 23, 24, 27, 28)
└── 2026-07/  (2 份: 01, 02)
```

## 报告库
14 份深度蒸馏报告在 `reports/` 目录 (也同步在 AGI-Super-Team): R01-R14。

## 仓库同步
详见 [sync-procedure.md](references/sync-procedure.md)。简述:
```bash
rsync -av --exclude='data/' --exclude='__pycache__/' \
  --exclude='*.jsonl' --exclude='*.jsonl.*' --exclude='*.gz' \
  /home/aa/.hermes/profiles/cqo/skills/5minbtc/ \
  /home/aa/clawd/repos/AGI-Super-Team/skills/5minbtc/
cd /home/aa/clawd/repos/AGI-Super-Team
git add skills/5minbtc/ && git commit -m "sync(skills/5minbtc): <版本>" && git push origin master
```

## 回测系统
```
backtest/
├── fetch_data.py            # Binance 历史数据下载
├── run_backtest.py          # v5.6 回测 (因子无预测力, 公平回测)
├── run_backtest_v57.py      # v5.7 回测 (含前视偏差, 已知)
├── run_backtest_v58.py      # v5.8 回测 (真实 1min 半 K线, 零前视) ← 推荐
├── run.sh                   # 一键运行
├── data/                    # 5min (105K) + 1min (259K) K线
└── results/                 # 回测结果 (gitignore)
```

## 文件结构
```
5minbtc/
├── SKILL.md                      # 本文件 (~160 行 INDEX)
├── 5minbtc-engine-v5.7.py        # 主引擎 (v5.7.4 规则, cron 调用)
├── 5minbtc-news.py               # 新闻扫描 (CoinDesk RSS, 唯一稳定源)
├── 5minbtc-log.py                # 日志记录 (写入 logs/)
├── archive/                      # 归档
│   └── engines/
│       └── 5minbtc-engine-v5.py  # v5 旧版 (回测因子模块 import)
├── logs/                         # 日志输出
│   ├── 5minbtc-log.jsonl         # 当前活跃 (cron 写入)
│   ├── 5minbtc-log.jsonl.1       # 最新备份
│   └── 5minbtc-log.jsonl.{2..22}.gz  # 历史归档
├── reviews/                      # 每日复盘 (按月归档)
│   ├── 2026-05/  (6 份)
│   ├── 2026-06/  (15 份)
│   └── 2026-07/  (2 份)
├── references/                   # 24 份专项 ref
├── backtest/                     # 回测系统
├── data/                         # 运行时 (news-risk-level.json 等)
├── scripts/                      # 复盘/工具脚本
└── reports/                      # 14 份蒸馏报告 (R01-R14)
```

---
最后更新: 2026-07-05 — 清理 news.py 死代码 (-54%) + SKILL.md 重构为 INDEX (-78%)
