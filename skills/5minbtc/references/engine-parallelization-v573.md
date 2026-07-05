# Engine Parallelization — v5.7.3

> 2026-06-17: 引擎HTTP请求从串行改为4路ThreadPoolExecutor并行

## 动机

用户反馈"5minbtc预测回复太慢"。链路分析：
- 引擎12-18s（4个串行HTTP：klines→depth→FNG→chainlink）
- 新闻扫描4s
- 网页搜索4s
- LLM分析+日志3s
- 总计22-29s

引擎HTTP是主瓶颈（占50%+）。新闻和搜索已与引擎并行发射，但引擎内部仍串行。

## 改造

```python
from concurrent.futures import ThreadPoolExecutor

def _fetch_fng():
    """P0-2黑天鹅过滤: FNG (parallel-safe)"""
    ...

def run():
    info = current_candle_info()

    # v5.7.3: 4路并行HTTP
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_klines = ex.submit(fetch_klines, limit=200)  # ← keyword arg!
        f_depth  = ex.submit(fetch_depth)
        f_fng    = ex.submit(_fetch_fng)
        f_cl     = ex.submit(fetch_chainlink_ref)

        candles = f_klines.result()
        depth = f_depth.result()
        fng = f_fng.result()
        chainlink_ref, cl_source = f_cl.result()

    # ... rest of run() unchanged
```

## 性能对比

| 版本 | 引擎耗时 | 全链路 |
|------|---------|--------|
| v5.7.1 串行 | 12-18s | 22-29s |
| **v5.7.3 并行** | **~3.0s** (实测avg) | **~7s** |
| 提速 | **4-5x** | **~3x** |

实测3次：2.92s, 3.05s, 3.03s。瓶颈从引擎→分析，全链路可感知。

## 🔴 Pitfall: ThreadPoolExecutor.submit() 的 positional arg 陷阱

```python
# ❌ WRONG: 200 被当作 symbol 参数
f_klines = ex.submit(fetch_klines, 200)
# 最终 URL: ?symbol=200&interval=5m&limit=200 → HTTP 400

# ✅ CORRECT: 用 keyword arg
f_klines = ex.submit(fetch_klines, limit=200)
# 最终 URL: ?symbol=BTCUSDT&interval=5m&limit=200
```

`ex.submit(fn, arg)` 中 `arg` 是 positional，按函数签名顺序匹配。如果函数定义为 `fetch_klines(symbol="BTCUSDT", interval="5m", limit=200)`，那么 `ex.submit(fetch_klines, 200)` 会把 200 传给 `symbol`。

**规则**: 所有非第一个参数的 submit 调用必须用 keyword args。

## 关键设计决策

- `_fetch_fng()` 提取为独立函数 — `ex.submit` 需要可 picklable 的函数，不能是 lambda 或内联
- `fng` 返回值格式保持 `{"value": int|None, "label": str|None}` — 与 `run()` 原有逻辑兼容
- Chainlink offset 逻辑不变 — `f_cl.result()` 返回 `(price, source)` tuple，与原来的 `fetch_chainlink_ref()` 返回值一致
- `closes` 列表构建放在 `.result()` 之后 — 必须在 candles 可用后才能计算
