# 5minbtc 版本变更日志

> 详细 changelog。SKILL.md 只保留当前版本亮点。

## v5.7.4 变更 (2026-06-18) — TREND强趋势decel极值约束


**2026-06-18 00:10 candle mispredict复盘驱动**

| 变更项 | 详情 | 根因 |
|--------|------|------|
| TREND decel约束 | EMA delta>$100的强TREND中，\|decel\|>0.7必须配合\|half_body\|>0.15同向才可翻转方向 | 00:10 candle: EMA delta=+$188, decel=-0.801, half_body=+0.009十字星, engine=neutral。LLM基于decel+position覆盖bear→实盘收涨❌。强趋势中decel减速是正常呼吸，十字星=空方无力 |
| LLM覆盖纪律 | engine=neutral/weak(score≈0)且regime=TREND时，decel极值不能单独作为方向翻转依据 | 仅decel+position在强TREND中是不够的——需要half_body实体确认 |

**关键洞察**: decel测量的是价格变化率的变化——在强趋势中，短暂减速后继续同向是常态而非反转。仅当half_body确认实际方向已改变(实体>ATR×0.15)时，decel极值才构成有效反转信号。



## v5.7.3 变更 (2026-06-17) — 引擎HTTP并行化


**用户反馈"预测太慢"→引擎4路并行HTTP提速 4-5x**

| 变更项 | 详情 | 效果 |
|--------|------|------|
| ThreadPoolExecutor(max_workers=4) | 4个HTTP调用(klines+depth+FNG+chainlink)并行发射 | 引擎12-18s→~3.0s |
| `_fetch_fng()` 独立函数 | 并行化需要picklable的函数引用 | 不破坏原有逻辑 |
| 全链路提速 | 引擎+新闻+搜索并行→全链路~7s | 之前22-29s，提速~3x |

**关键pitfall**: `ex.submit(fetch_klines, 200)` 把 `200` 传给第一个参数 `symbol`→HTTP 400。必须用 `ex.submit(fetch_klines, limit=200)`。

详见 `references/engine-parallelization-v573.md`。



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



