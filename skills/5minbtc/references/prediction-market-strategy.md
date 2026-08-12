# 预测市场盈利策略 — 5minbtc 方向信号 × 币安 Up/Down 5m

> 把 5minbtc 的方向预测 (bull/bear) 用到币安 Web3 预测交易 (BTC Up/Down 5m,
> Polymarket 式二元市场) 的**完整策略**。引擎方向 + 价格门控 + 凯利仓位。
> ⚠️ 预测交易无 test 模式 — paper 模拟先用, 实盘前务必先跑 paper。

## 一、唯一公式

```
每 $1 下注 EV = p − P
p = 你该方向的真实概率（条件胜率，非引擎 conf）
P = 你买入 token 的价位（市场 ask）
只当 p > P + 手续费 才下注
```

**利润不是来自"方向准"，是来自"你比市场定价准"。**

## 二、p 校准（2026-08-12 实测，第 2 分钟预测）

| 信号 | 条数 | 胜率 p | 盈亏平衡入场价 |
|------|------|--------|--------------|
| **bull → UP** | 23 | **74%** | 0.70 |
| bear → DOWN | 7 | 57% | 0.57 |

**关键事实**（详见 `5minbtc_day_stats.py` / `logs/5minbtc-log.jsonl`）：
- 预测全部发生在**第 2 分钟 (progress ~40%)** —— watch 每根 K 线只记录首次采样。所以 p 是**早期预测**的准确率，不是"看了一半结果"刷出来的。
- **引擎 confidence 反校准**：conf<50 胜率 72% > conf 50-59 的 67%。**不要用 conf 当门槛**（trader 默认 MIN_CONF=55 实测反而砍样本降准确率）。
- DOWN 样本仅 7 笔，57% 不可靠 → **先只做 bull/UP**。

## 三、入场规则（价格门控 = 一切）

```
第 2 分钟 bull 信号:
  实时 ask ≤ 0.65  → 买 UP  (p=0.74 − 9% margin − 手续费)
  实时 ask ≥ 0.70  → 不碰
bear 信号: ask ≤ 0.50 才买，否则跳过
```

- **limit-price = 入场上限**（UP 0.65 / DOWN 0.50，已是脚本默认），行为 = "按最优价买，绝不高于上限"，秒成交不追高。
- 不要用 ask×0.98 省 2% —— 5 分钟市场波动快，挂低 2% 大概率不成交，**错过整笔 EV+0.15~0.19 的交易**。
- LIMIT 单 ≥0.5U（交易所仅 MARKET 强制 ≥1.5U；脚本已放开 LIMIT 下限）。

## 四、仓位（1/4 凯利）

```
凯利 f* = (p − P)/(1 − P)
p=0.74, P=0.55 → f*≈42% → 实盘用 1/4 ≈ 10% 账户/注
每根 K 线最多 1 注 | 账户 10U 用 1U/注
```

74% 胜率 = 约 3/10 注会全亏本金 —— **控制仓位是活命前提**。

## 五、持有到结算，无 TP/SL

二元市场几分钟结算成 1 或 0：
- **TP 关**：中途 1.3× 止盈是拿确定的钱换掉大概率到手的 1.0，负期望。
- **SL 关**：错时 token 结算到 0，0.4× 止损和持有到 0 差别极小。
- 真正的"止损" = **入场价纪律**（ask 超上限就不买）。

## 六、paper 模拟（先用这个，绝不下单）

```bash
# 单次：结算已收盘 → 引擎信号 → 真实报价 → 价格门控记录 → 报告
python3 scripts/5minbtc_trader.py --paper --paper-up-max 0.65 --paper-push

# 实时监控：LIMIT 单模拟 → 设单/成交/未成交 → 盘中实时盈亏% → 结算，推 Telegram
python3 scripts/5minbtc_trader.py --paper-monitor --paper-up-max 0.65 \
  --paper-p-down 0.50 --paper-push
```

- 状态文件 `~/bb-auto/5minbtc-paper.json`（含入场 P / 成交价 / 结算 PnL / 未成交记录）
- 只 get-quote / order-book，**从不 place-order**
- 需要的环境变量：`BINANCE_API_KEY / BINANCE_API_SECRET / BINANCE_PREDICT_WALLET / BINANCE_PREDICT_WALLET_ID`
- **实时价格**：`scripts/prediction_ws_feed.py` 用币安 **w3w-prediction WebSocket API**
  （`wss://api.binance.com/sapi/wss?topic=web3_prediction_orderbook_data`，<200ms）
  写 `~/bb-auto/prediction-ws.json` 缓存；watch/paper 读缓存即秒级实时。不用 RSS。
  认证: HMAC SHA256 签名 + `X-MBX-APIKEY` header; 30s PING; 断线重连。

## 七、实时推送格式（--paper-monitor, LIMIT 单模拟）

```
📋 LIMIT 单已设 | 19:32 p40%            ← 设单: 限价 + 现价参考
UP 限价 0.65 (p=0.74) | 现价 0.72
成交时 EV = +0.09 | 等回调

✅ 成交 | UP @ 0.60 (限价 0.65)         ← 成交: 记录真实成交价
入场 P = 0.60 | p = 0.74 | EV = +0.14
假设 1 USDT

❌ 未成交 | UP 限价 0.65                ← 收盘未触及: 放弃该笔
收盘仍未触及限价

📡 实时 | UP @0.60 → 现价 0.78          ← 盘中: 实时盈亏%
实时盈亏 +30.0% | 剩余 2m40s

🏁 结算 19:35 UP @0.60 ✅ 中            ← 收盘: 最终获利%
最终 PnL: +66.7% | $+0.67
```

## 八、诚实局限

- p 是**单日 30 笔**样本，会回归；数据积累几百根后重估。
- **盈利取决于真实 ask vs p 的差距**——paper 模拟（真实报价）是唯一能验证"市场是否低估你的信号"的手段。实测第 2 分钟市场通常还没充分定价，这是 edge 所在，但必须量化确认。
- 首次实盘前：paper 连续证明 EV+ 至少 2-3 天。

## 相关
- [prediction-trading-cli.md](prediction-trading-cli.md) — CLI 全参数/安全契约/API端点
- [polymarket-data-source.md](polymarket-data-source.md) — Polymarket 用 Chainlink 结算（与 Binance 价差风险）
