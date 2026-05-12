---
name: relayer-trade
description: Polymarket链上交易skill。通过Relayer v2 API绕过CLOB geo-block，执行buy(split)/sell(merge+transfer)/redeem/claim。零CLOB依赖，纯链上gasless。Triggers: 'relayer buy', 'relayer sell', 'relayer claim', '链上交易', 'split position', 'merge position', 'geo-block bypass'.
---

# Relayer Trade Skill — Polymarket链上Gasless交易

**绕过CLOB geo-block的终极方案。** Relayer v2 不做IP检查。

## 脚本目录

```
skills/relayer-trade/scripts/
└── relay_trade.js    # 链上交易主脚本
```

**依赖**: `/tmp/node_modules/` (@polymarket/builder-relayer-client, viem)

## 命令

```bash
# Buy YES (split USDC → YES+NO tokens)
node "$SKILL_DIR/scripts/relay_trade.js" buy <conditionId> <amount_in_usdc>

# Sell YES (merge YES+NO → USDC)
node "$SKILL_DIR/scripts/relay_trade.js" sell <conditionId> <amount>

# Sell YES (transfer to counterparty)
node "$SKILL_DIR/scripts/relay_trade.js" transfer <yes_token_id> <to_address> <amount>

# Approve USDC for CTF
node "$SKILL_DIR/scripts/relay_trade.js" approve-usdc

# Approve CTF tokens for adapter
node "$SKILL_DIR/scripts/relay_trade.js" approve-ctf <spender_address>

# Redeem settled positions (claim)
node "$SKILL_DIR/scripts/relay_trade.js" redeem <conditionId> <yes_amount> <no_amount> [neg_risk]

# Check redeemable positions
node "$SKILL_DIR/scripts/relay_trade.js" check-redeemable

# Test connectivity
node "$SKILL_DIR/scripts/relay_trade.js" ping
```

## 认证

凭证在 `.env.poly`：`POLY_PRIVATE_KEY` + `POLY_PROXY_WALLET` + `POLY_BUILDER_API_KEY`

SDK自动生成 HMAC-SHA256 签名 headers。

## 交易模式

| 操作 | CLOB | Relayer链上 |
|------|------|------------|
| 买入YES | post_order() → 撮合 | splitPosition() → USDC铸造YES+NO |
| 卖出YES | post_order() | mergePositions() 或 transferFrom() |
| Claim | Browser | redeemPositions() via NegRiskAdapter |

**限制**: split买入=1:1铸造(无折扣)；卖出需NO tokens或对手方

## 合约地址

| 合约 | 地址 |
|------|------|
| USDC.e | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |
| CTF | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` |
| NegRisk Adapter | `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296` |

## NegRisk市场

negRisk市场使用 `NegRiskAdapter.splitPosition/mergePositions/redeemPositions`，非标准CTF路径。

判断: `curl gamma-api/markets?slug=xxx → negRisk: true/false`
