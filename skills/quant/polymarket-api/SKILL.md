---
name: polymarket-api
description: Polymarket交易操作。下单/卖单/撤单/查余额/查订单/Claim结算。优先Relayer API执行链上操作，CLOB API用于读操作+订单管理。零browser零gas，纯API直连。Triggers: 'polymarket交易', 'API下单', 'buy YES', 'sell NO', 'claim', 'poly trade', 'poly_trade'.
---

# Polymarket API Trading Skill

**零browser、零gas、纯API交易。** Relayer执行链上操作（claim/redeem），CLOB管理订单（buy/sell/cancel）。

## ⚠️ 优先级准则

**所有写操作优先用Relayer API**（gasless链上执行），CLOB API作为读操作+订单管理的补充：

| 操作类型 | 首选 | 备选 | 说明 |
|----------|------|------|------|
| **Claim结算** | Relayer `execute()` | — | redeemPositions，唯一方式 |
| **Buy/Sell下单** | CLOB `post_order()` | — | 链下订单簿撮合 |
| 撤单 | CLOB `cancel()` | — | 取消未成交挂单 |
| 查余额 | CLOB `get_balance()` | — | 读操作 |
| 查持仓 | CLOB trades + data-api | — | 读操作 |
| 查价格 | CLOB `get_price()` | — | 读操作 |
| 查挂单 | CLOB `get_orders()` | — | 读操作 |

**Browser仅作为最终fallback**（登录态过期时才需要）。

## 前置

凭证文件 `.env.poly`（已配置，勿修改）：
```
POLY_PRIVATE_KEY=0x...
POLY_PROXY_WALLET=0x...
POLY_API_KEY=...
POLY_API_SECRET=...
POLY_API_PASSPHRASE=...
```

SDK已安装：
- `py-clob-client` — CLOB订单管理（buy/sell/cancel/查余额/查价格）
- `py-builder-relayer-client` — Relayer链上操作（claim/redeem/deploy）
- `py-builder-signing-sdk` — 签名SDK（relayer依赖）
- `python-dotenv`

## 核心脚本

```bash
cd /home/aa/.openclaw/workspace-quant

# === 读操作 (CLOB API) ===

# 查余额
python3 skills/polymarket-api/scripts/poly_trade.py balance

# 查价格
python3 skills/polymarket-api/scripts/poly_trade.py price <TOKEN_ID>

# 查挂单
python3 skills/polymarket-api/scripts/poly_trade.py orders

# === 写操作 (CLOB API — 订单簿) ===

# 买YES（买涨/买跌概率）
python3 skills/polymarket-api/scripts/poly_trade.py buy <YES_TOKEN_ID> YES <price> <size>

# 买NO（反向）
python3 skills/polymarket-api/scripts/poly_trade.py buy <YES_TOKEN_ID> NO <price> <size>

# 卖出
python3 skills/polymarket-api/scripts/poly_trade.py sell <TOKEN_ID> <price> <size>

# 撤单
python3 skills/polymarket-api/scripts/poly_trade.py cancel <ORDER_ID>

# === 链上操作 (Relayer API — 优先) ===

# Claim已结算仓位（赎回资金到现金余额）
python3 skills/polymarket-api/scripts/poly_relay.py claim [CONDITION_ID]
# 不传condition_id = claim全部可赎回仓位

# 查询可Claim仓位列表
python3 skills/polymarket-api/scripts/poly_relay.py redeemable
```

## Relayer操作指南

### 初始化
```python
from dotenv import load_dotenv; load_dotenv('.env.poly')
from py_builder_relayer_client.client import RelayClient
from py_builder_signing_sdk.config import BuilderConfig
from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds
from py_builder_relayer_client.models import SafeTransaction, OperationType

creds = BuilderApiKeyCreds(
    key=os.environ['POLY_API_KEY'],
    secret=os.environ['POLY_API_SECRET'],
    passphrase=os.environ['POLY_API_PASSPHRASE'],
)
config = BuilderConfig(local_builder_creds=creds)

client = RelayClient(
    relayer_url='https://relayer.polymarket.com',
    chain_id=137,  # Polygon mainnet
    private_key=os.environ['POLY_PRIVATE_KEY'],
    builder_config=config,
)
```

### Claim/Redeem已结算仓位
已结算的市场需要通过Relayer调用链上`redeemPositions`赎回USDC到钱包余额。

**⚠️ Geo-block注意**: Relayer和CLOB写操作均受Polymarket地区限制，需要非限制区网络环境。

## 完整交易流程

### Step 1: 获取市场Token ID

```python
import json
from dotenv import load_dotenv; load_dotenv('.env.poly')

# 方法A: 按slug查
import subprocess
slug = "ethereum-above-on-march-25"
r = subprocess.run(["curl", "-s", "--noproxy", "*", "--max-time", "3",
    f"https://gamma-api.polymarket.com/events?slug={slug}"],
    capture_output=True, text=True)
data = json.loads(r.stdout)

for e in data:
    for m in e['markets']:
        q = m['question']
        p = json.loads(m['outcomePrices'])
        tokens = json.loads(m['clobTokenIds'])
        yes_tok, no_tok = tokens[0], tokens[1]
        yes_price, no_price = float(p[0]), float(p[1])
        # 找到目标market后记录token_id
```

```python
# 方法B: 搜索
r = subprocess.run(["curl", "-s", "--noproxy", "*", "--max-time", "5",
    "https://gamma-api.polymarket.com/public-search?q=bitcoin+above+march+25&limit=5"],
    capture_output=True, text=True)
data = json.loads(r.stdout)
for e in data['events']:
    # 遍历markets找目标 → 提取clobTokenIds
```

**⚠️ curl必须加 `--noproxy '*'`**（Tailscale Funnel劫持DNS）

### Step 2: 查价格+订单簿

```bash
python3 skills/polymarket-api/scripts/poly_trade.py price <TOKEN_ID>
# 输出: BID: 0.94 | ASK: 0.96 | MID: 0.95
```

**定价策略：**
- `MID` = 中间价，挂MID大概率成交
- `BID` = 最高买价，挂BID等待
- `ASK` = 最低卖价，挂ASK立即成交
- **推荐挂MID或略高于BID**（1-2¢溢价换速度）

### Step 3: 下单

```bash
# 买10份YES @ $0.95（花费$9.50）
python3 skills/polymarket-api/scripts/poly_trade.py buy <YES_TOKEN_ID> YES 0.95 10

# 买10份NO（自动切换到NO token）
python3 skills/polymarket-api/scripts/poly_trade.py buy <YES_TOKEN_ID> NO 0.05 10
```

输出 `✅ FILLED` = 即时成交，`📤 LIVE` = 挂单等待对手盘。

### Step 4: 验证

```bash
python3 skills/polymarket-api/scripts/poly_trade.py balance   # 检查余额扣减
python3 skills/polymarket-api/scripts/poly_trade.py orders    # 检查挂单状态
```

## 铁律

| 规则 | 说明 |
|------|------|
| **Relayer优先** | 链上操作（claim/redeem）用Relayer，不依赖browser |
| `fee_rate_bps=1000` | Polymarket标准10%手续费，**不可改** |
| `signature_type=1` | POLY_PROXY模式，**不可改** |
| `--noproxy '*'` | curl必须加，Tailscale劫持Gamma/CLOB DNS |
| size单位 = shares | 10 shares @ $0.95 = 花费$9.50 |
| price范围 = 0.01-0.99 | 超出范围会被拒 |
| **Geo-block** | CLOB写操作+Relayer均受地区限制，需非限制区IP |

## 仓位管理集成

交易后立即更新：
1. `data/profit-peaks.json` — 记录买入价作为峰值
2. `memory/YYYY-MM-DD.md` — 记录交易详情
3. 仓位监控cron下次运行会自动跟踪止盈止损

## 常见问题

| Error | 解决 |
|-------|------|
| `'dict' has no attribute` | SDK返回dict非对象，用`['key']`访问 |
| `Connection timeout` | 加`--noproxy '*'`或检查Tailscale |
| `403 Trading restricted` | Geo-block，需切换非限制区IP |
| `SSL EOF / Connection refused` | Relayer geo-block，同上 |
| `invalid authorization` | 检查.env.poly凭证是否过期 |
| `not enough balance` | 余额不足，`poly_trade.py balance`检查 |
| `matched: 0/N` | 挂单未成交，cancel后提高价格重挂 |
| `Proxy not deployed` | 首次需调用`client.deploy()`部署Safe |

## 变更记录
- v2.0 (2026-03-25): 加入Relayer API优先准则，新增claim/redeem操作说明，geo-block文档
- v1.0 (2026-03-24): 初版，CLOB API交易
