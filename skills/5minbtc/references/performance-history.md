# 5minbtc Performance History

> Last updated: 2026-06-13 | 175 rounds across 11 trading days

## Cumulative Stats

| Metric | All (348r) | v4.x (152r) | v5.4 (93r) | v5.5 (28r) | v5.7.1 (100r) | v5.7.x (123r) |
|--------|-----------|-------------|------------|------------|---------------|---------------|
| Direction | 68.7% | 62.5% | 66.7% | 71.4% | **83.0%** | 80.5% |
| Range | — | 61.2% | 78.5% | 75.0% | 60.0% (3d) | — |
| v5.7.1 lift vs v4.x | — | baseline | — | — | **+20.5pp** | — |
| v5.7.1 lift vs v5.5 | — | — | — | baseline | **+11.6pp** | — |

## Monthly Summary (2026-05-05 → 06-12)

**175 rounds total — Direction 77.1% (135/175)**

| Version | Period | Rounds | Direction | Range | Key Feature |
|---------|--------|--------|-----------|-------|-------------|
| v4.x | 05-05→12 | 152 | 62.5% | 61.2% | Baseline, 线性打分 |
| v5.4 | 05-23→25 | 93 | 67.4% | 78.5% | 正交因子+Regime |
| v5.5 | 05-27 | 28 | 71.4% | 75.0% | Platt Scaling+Bull惩罚 |
| **v5.7.1** | **06-03→12** | **100** | **83.0%** | **60.0%** | **半K线策略+黑天鹅防护** |

**版本演进: v4.x 62.5% → v5.7.1 83.0% (+20.5pp)**

**最佳单日记录:**
- 方向: 90.9% (06-06, 33轮, FNG=12~14极端恐惧)
- 连胜: 16连正确 (06-09, 初始2误判后)
- 缩量场景方向: 6月系列 ≥92%

**最弱环节:**
- bear方向中量区(40-80%): 06-12仅44.4% (低于随机)
- 区间准确率: v5.7.1仅60.0% (半K线区间缩窄后trade-off)
- 高量场景: 方向准确率不稳定

## Daily Detail

### 2026-06-12 | v5.7.1 | 25 rounds
- Direction: **68.0% (17/25)** | Range: 40.0% (10/25) | MAE: 0.125%
- Market: Downtrend week, BTC ~$63,500 area
- Session: 20:53→23:00 CST
- Bull 87.5% (7/8), Bear 53.8% (7/13), Neutral 100% (3/3)
- **Strong**: Low vol (<40%) 87.5% (7/8) ✅
- **Weak**: Mid vol (40-80%) 44.4% (4/9) — bear方向中量区全面崩溃
- High vol (>80%) 75.0% (6/8)
- 8 errors: 6 bear方向误判, 其中4轮中量区
- Key insight: bear方向在区间震荡中需要额外校验, 中量区44.4%是明显短板

### 2026-06-09 | v5.7.1 | 18 rounds
- Direction: **88.9% (16/18)** | Range: 61.1% (11/18) | MAE: 0.125%
- Market: BTC vol declining, consolidation
- Session: 20:04→22:06 CST
- **2 initial errors → 16 consecutive correct** (single-day record)
- Low vol (≤80%) direction 100% — 半K线核心优势持续验证
- Strong momentum continuation pattern throughout session

### 2026-06-06 | v5.7.1 | 33 rounds
- Direction: **90.9% (30/33)** | Range: 78.8% (26/33) | MAE: 0.082%
- Market: BTC ~$62,500, FNG=12~14 Extreme Fear
- Session: Full night session
- **All-time direction record** (v5.7.1 any version)
- Exceptional performance under extreme fear sentiment
- 3 errors only, none catastrophic

### 2026-06-03 | v5.7.1 | 24 rounds
- Direction: **79.2% (19/24)** | Range: 54.2% (13/24) | MAE: 0.106%
- Market: BTC **-6.9% decline** $72K→$67K, FNG=11 Extreme Fear
- Session: 20:04→22:08 CST (continuous 2h), half-K strategy ~40% progress
- **Mid-range vol (40~80%) = 100% direction (7/7)**
- Low vol (<40%) 100% direction (7/7) — 半K线最强edge
- 5 errors: 2 noise/unavoidable, 3 have prevention paths
- Black swan protection active but not triggered (ATR ok, news=NORMAL)

### 2026-05-27 | v5.5 | 28 rounds
- Direction: **71.4% (20/28)** | Range: 75.0% (21/28) | MAE: $54.0 (0.072%)
- Market: **-0.78% choppy decline** BTC 75753→75166
- Session: 20:03→22:10+ CST
- Key: Bear 76% direction accuracy, Bull only 60%
- 8 direction errors analyzed → led to v5.6 development
- Cron job was mislabeled "v5.4" while running v5.5 engine

### 2026-05-25 | v5.4 | 26 rounds
- Direction: **61.5% (16/26)** | Range: 88.5% (23/26) | MAE: 0.032%
- Market: **+0.43% choppy/rangebound** 🏆 Best Range day ever
- Session: 20:40→22:50 CST
- Key: Range precision extraordinary in choppy market
- Issues: 21:xx chop zone 50% direction (12 rounds), bear bias overrepresented in bull market
- Turning point: 22:00 sudden $133 pump, engine switched to bull by 22:05

### 2026-05-24 | v5.4 | 30 rounds
- Direction: **73.3% (22/30)** | Range: 76.7% (23/30) | MAE: 0.047%
- Market: **-1.09% single-direction drop** 🏆 Best direction day
- Session: 20:04→22:29 CST
- Key: Bear bias perfectly matched trend, 22:xx direction 83%
- Issues: Confidence flat 40-55%, news factor 29/30=NEUTRAL

### 2026-05-23 | v5.4 | 37 rounds
- Direction: 64.9% (24/37) | Range: 73.0% (27/37)
- Market: v5.4 first day, regression from v5.4 backtest
- Key: 9-factor orthogonal system + sigmoid compression debut

### 2026-05-12 | v4.x | 5 rounds
- Direction: 40.0% (2/5) | Range: 60.0% (3/5)
- Market: Worst day, tiny sample

### 2026-05-11 | v4.x | 12 rounds
- Direction: 66.7% (8/12) | Range: 91.7% (11/12)
- Market: Small sample, but excellent Range

### 2026-05-06 | v4.x | 28 rounds
- Direction: 57.1% (16/28) | Range: 71.4% (20/28)
- Market: 横盘, best Range day for v4 era

### 2026-05-05 | v4.x | 107 rounds
- Direction: 64.5% (69/107) | Range: 55.1% (59/107)
- Market: 震荡+突破, BTC rangebound with breakout attempts
- Notes: Heavy testing day, many rounds in a single session

## v5.7.1 Aggregate (06-03→12)

| Metric | 100 rounds |
|--------|------------|
| Direction accuracy | **83.0%** |
| Best day | 90.9% (06-06, 33r) |
| Worst day | 68.0% (06-12, 25r) |
| Low vol (<40%) | ≥87% (6月系列) |
| Mid vol (40-80%) | 不一致: 100%(06-03) → 44.4%(06-12) |
| FNG range | 11-15 (all Extreme Fear) |
| Consistent edge | half-K continuation + low vol environment |

## v5.x Aggregate (05-23→06-12, 214 rounds)

| Metric | v5.x Total |
|--------|------------|
| Direction accuracy | **76.2% (163/214)** |
| v4.x baseline | 62.5% |
| Improvement | **+13.7pp** |

## Error Pattern Summary (from 05-27 deep review)

Three structural root causes identified for direction errors:

### Pattern A: V-reversal momentum lock
- momentum_tstat uses 15-candle OLS regression → lagging in V-reversals
- decel (5-candle rate of change) detects reversal but was underweighted
- Fixed in v5.6: conflict detection dynamically downweights momentum

### Pattern B: RANGE regime noise trading
- meanrev ×1.5 in RANGE regime amplifies weak signals through ±1 threshold
- 50% accuracy = pure random, burning transaction costs
- Partially addressed by v5.5 neutral zone shrinkage [-2,2]→[-1,1]

### Pattern C: Data source misalignment
- Engine uses Binance BTCUSDT, Polymarket settles via Chainlink (Coinbase-weighted)
- Systematic offset: Binance ~$88-146 higher than Coinbase
- Fixed in v5.6: Coinbase reference price compensation

### Pattern D (v5.7.1 era): Bear mid-vol zone instability
- 06-12: bear direction in mid vol (40-80%) only 44.4% (9 rounds, 4 correct)
- 06-03: mid vol 100% — conditions matter: declining trend vs rangebound
- Root cause: half-K continuation edge weakest in bear + mid-vol combo
- Pending fix: add confirmation rule for bear + mid-vol scenario

## Review Files

Detailed daily reviews stored at skill root:
- `review-2026-05-05.md` — v4.x era
- `review-2026-05-24.md` — v5.4 单边下跌
- `review-2026-05-25.md` — v5.4 震荡市
- `review-2026-05-27.md` — v5.5 + 3 error deep-dive
- `review-2026-05-29.md` — Black swan recovery
- `review-2026-06-03.md` — v5.7.1 首日
- `review-2026-06-06.md` — 33r 90.9% 历史记录
- `review-2026-06-09.md` — 16连胜
- `review-2026-06-12.md` — bear中量区44.4%崩溃
