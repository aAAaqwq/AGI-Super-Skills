# 币安预测交易 CLI — 5minbtc_trader.py 使用文档

> 5minbtc 引擎信号 → 币安「Web3 Wallet 预测交易」(BTC Up or Down 5m, Polymarket 式二元市场) 桥接。
> 引擎 `bias=bull` → 买 UP token; `bias=bear` → 买 DOWN token。
> ⚠️ **预测交易没有 test 模式 — 下单即真实花钱。** 非投资建议,仅供量化研究。

## 定位

- 脚本: `scripts/5minbtc_trader.py`(纯 Python 标准库, 直接签名调用币安 SAPI)
- 引擎: `5minbtc-engine-v5.7.py`(预测方向/置信度/taker_buy)
- 监控: `scripts/5minbtc-monitor.py`(看信号事件, 不交易; 见 monitoring-claude-code.md)

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | ✅ | 签名用 (HMAC SHA256) |
| `BINANCE_PREDICT_WALLET` | ✅ | 预测钱包地址 (从环境变量注入, 代码不含默认值) |
| `BINANCE_PREDICT_WALLET_ID` | ✅ | 预测钱包 ID (同上) |

> 钱包地址/ID 属于账户敏感信息, 不走代码/仓库, 必须由运行方 export。
> 查询方式: 用 key 调 `GET /sapi/v1/w3w/wallet/prediction/wallet/list` 获取。

## 核心参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--once` | - | 单次: 读引擎→判信号→发现市场→报价→(确认后)下单 |
| `--loop` | - | 持续监控开仓 (每根K线第2/3/4分钟采样) |
| `--monitor` | - | 持仓监控: 实时面板 + 自动止盈止损 |
| `--live` | off | 实盘 (双确认: 启动 yes + 每单 y) |
| `--amount` | 2.0 | 下单金额 USDT (LIMIT ≥0.5, MARKET ≥1.5) |
| `--order-type` | `LIMIT` | 买入单类型: LIMIT / MARKET |
| `--limit-price` | 默认=入场上限 | LIMIT 限价 (token 价 0~1); 不传则用该方向入场上限 (`--limit-up-max`/`--limit-down-max`) |
| `--limit-up-max` / `--limit-down-max` | 0.65 / 0.50 | 该方向入场上限 = LIMIT 默认限价 (实测盈亏平衡 UP 0.70 / DOWN 0.57) |
| `--tp-mult` | 0(不启用) | 止盈: 现价/成本 ≥ 此值自动 SELL 锁利 (如 1.4=+40%) |
| `--sl-mult` | 0(不启用) | 止损: 现价/成本 ≤ 此值自动 SELL (如 0.4=跌60%) |
| `--monitor-interval` | 10 | 持仓监控轮询间隔秒 |
| `--monitor-iters` | 无限 | 持仓监控轮数上限 |
| `--rounds` | 无限 | loop 轮数上限 |

## 用法示例

```bash
# 1. 单次 LIMIT 低挂买入 (只报价, 确认后才成交)
python3 scripts/5minbtc_trader.py --once --order-type LIMIT --amount 2.0

# 2. 持续监控开仓 (每根K线第2/3/4分钟, LIMIT 低挂)
python3 scripts/5minbtc_trader.py --loop

# 3. 持仓监控 + 自动止盈止损 (需显式 TP/SL + --live 才真实卖出)
python3 scripts/5minbtc_trader.py --monitor --tp-mult 1.4 --sl-mult 0.4 --live

# 4. 只跑 1 轮面板看当前持仓 (不自动卖)
python3 scripts/5minbtc_trader.py --monitor --monitor-iters 1

# 5. 实盘单次 (启动输 yes, 每单输 y)
python3 scripts/5minbtc_trader.py --once --live --amount 2.0
```

## 安全契约 (铁律)

1. **默认只报价不成交** — get-quote 不花钱, 真实花钱的是 place-order-bundle
2. **买入需人工确认** — 每单输入 y; `--live` 另需启动时输入 yes (双闸门)
3. **自动卖出需显式 TP/SL** — 未设 `--tp-mult`/`--sl-mult` 禁止自动 SELL, 只监控提示
4. **自动止盈止损**: 现价/成本 ≥tp 自动 SELL 锁利; ≤sl 自动 SELL 止损 (用户授权自动卖出)
5. **重试机制**: `_retry` 默认 10 次指数退避, 覆盖持仓查询/盘口/卖出, 避免单次失败
6. **余额校验**: 下单前检查, 不足即拒; 金额默认小注
7. **市场过期保护**: 每根K线只对当前 OPEN 的 btc-updown-5m 市场取价/下单 (endDate 硬校验)
8. **token 映射防错**: order-book outcome 强制校验 + 词首匹配, 不符拒单

## 币安预测 API 端点 (已验证)

| 端点 | 用途 |
|---|---|
| `GET /sapi/v1/w3w/wallet/prediction/wallet/list` | 预测钱包列表 |
| `GET /sapi/v1/w3w/wallet/prediction/balance/payment-options` | 余额 (CeDeFi/SPOT/FUNDING) |
| `GET /sapi/v1/w3w/wallet/prediction/market/list` | BTC 5m 涨跌市场列表 |
| `GET /sapi/v1/w3w/wallet/prediction/order-book` | token 盘口价 (需 marketId+tokenId+vendor=predict_fun) |
| `POST /sapi/v1/w3w/wallet/prediction/trade/get-quote` | 报价 (BUY/SELL, LIMIT/MARKET) |
| `POST /sapi/v1/w3w/wallet/prediction/trade/place-order-bundle` | 下单 (真实花钱, FOK/GTC) |
| `GET /sapi/v1/w3w/wallet/prediction/position/list` | 持仓查询 |
| `GET /api/v3/ticker/price?symbol=BTCUSDT` | BTC 实时价 (免签名) |

## 已知坑 (教训)

- **签名**: POST 用原始字节 body (`(qs+"&signature="+sig).encode()`), 库自动转义 `[]` 导致 -1022
- **amountIn**: 18 位 wei 字符串; MARKET 单 ≥1.5e18 (~1.5 USDT), LIMIT 单不受此限
- **LIMIT 单**: 需 `priceLimit` (token 价 0~1) + place-order 用 `GTC`; MARKET 用 `FOK`
- **SELL 无持仓**报 `-9000 exceeded available shares` = 报价参数正确, 只是无持仓可卖 (正常)
- **市场收盘**: 接近结算时 UP/DOWN token 价会极端 (0.98/0.01), 此时买入性价比差, 引擎 conf 通常也会拦截

## 验证快照 (2026-08-12)

- 余额: `payment-options` 返回 CeDeFi/SPOT/FUNDING 三账户 (具体数额运行时查询, 不写入文档)
- 市场: BTC Up or Down 5m, `tradingStatus=OPEN`, chainId 56 (BSC), vendor PREDICT_FUN
- 止盈止损触发逻辑 dry-run: 1.44x→止盈 ✅, 0.36x→止损 ✅, TP/SL 未设→不触发 ✅
- LIMIT 报价: `orderType=LIMIT`+`priceLimit` 返回 quoteId ✅
- SELL 无持仓时: `-9000 exceeded available shares` = 报价参数正确, 只是无持仓可卖 ✅

## Paper 模拟 & 实时监控 (2026-08-12 新增, 绝不下单)

> 预测交易无 test 模式, 用 `--paper` / `--paper-monitor` 先做真实报价模拟。
> 完整盈利策略见 [prediction-market-strategy.md](prediction-market-strategy.md)。

### `--paper` 单次模拟
```bash
python3 scripts/5minbtc_trader.py --paper [--paper-up-max 0.65] [--paper-down-max 0.55] \
  [--paper-fee 0.01] [--paper-push]
```
流程: 结算已收盘注单 → 引擎信号 → 真实 ask → **价格门控** (ask≤胜率-费才记录) → 报告。
状态文件 `~/bb-auto/5minbtc-paper.json`。参数:
| 参数 | 默认 | 说明 |
|---|---|---|
| `--paper-up-max` | 0.65 | UP 入场价上限 (实测盈亏平衡 ~0.70, 留 margin) |
| `--paper-down-max` | 0.55 | DOWN 入场价上限 (实测盈亏平衡 ~0.57) |
| `--paper-fee` | 0.01 | 单笔手续费比例 |
| `--paper-push` | off | 报告推 Telegram |
| `--paper-min-conf` | 0 | 置信度门槛 (实测 confidence 反校准, 默认不过滤) |
| `--paper-strength-gate` / `--paper-tb-filter` | off | 未经验证的过滤, 需单独开启 |

### `--paper-monitor` 实时监控
```bash
python3 scripts/5minbtc_trader.py --paper-monitor --paper-up-max 0.65 \
  --paper-p-down 0.50 --paper-push [--paper-poll 20] \
  [--paper-push-every 60] [--paper-push-delta 5]
```
每根 K 线: 信号触发→推送入场 P+机会判断(EV=p−P) → 盘中轮询实时盈亏% → 收盘推最终获利%。
| 参数 | 默认 | 说明 |
|---|---|---|
| `--paper-p-up` / `--paper-p-down` | 0.74 / 0.57 | 该方向预估概率 p (今日实测 bull/bear 胜率) |
| `--paper-poll` | 20 | 轮询秒数 |
| `--paper-push-every` | 60 | 实时盈亏最少推送间隔秒 |
| `--paper-push-delta` | 5 | 实时盈亏变化 ≥ 此百分比才推 |

### 信号判定差异 (paper 版)
`_signal()` 已参数化: `min_conf` / `tb_filter` / `strength_gate` 均可关。
**实测洞察**: 引擎 confidence 反校准 (conf<50 胜率 72% > conf 50-59 的 67%), 默认不设 conf 门槛;
预测全在第 2 分钟 (progress~40%), bull 74% / bear 57%。
