---
name: polymarket-api
description: Polymarket交易操作。统一入口scripts/trade.py，slug驱动，零browser纯API。Triggers: 'polymarket交易', 'API下单', 'buy YES', 'sell NO', 'trade', 'price', '仓位'.
---

# Polymarket API Trading Skill

**⚠️ 强制使用 `scripts/trade.py`，禁止直接调用CLOB API。**

## 脚本目录

```
skills/polymarket-api/scripts/
└── trade.py    # 统一交易入口（买/卖/查价/查仓位）
```

## 命令

```bash
# === 交易 ===
python3 "$SKILL_DIR/scripts/trade.py" buy <slug> <YES/NO/UP/DOWN> <金额> [--threshold N] [price]
python3 "$SKILL_DIR/scripts/trade.py" sell <slug> <YES/NO> <金额> [--threshold N] [price]

# === 查询 ===
python3 "$SKILL_DIR/scripts/trade.py" price <slug> <YES/NO> [--threshold N]
python3 "$SKILL_DIR/scripts/trade.py" info <slug> [--threshold N]
```

## 示例

```bash
# BTC>$68k Mar28 买NO $10
python3 "$SKILL_DIR/scripts/trade.py" buy bitcoin-above-on-march-28 NO 10 --threshold 68000

# BTC涨跌盘 买DOWN $8
python3 "$SKILL_DIR/scripts/trade.py" buy btc-up-or-down-on-march-27-2026 DOWN 8

# 查价
python3 "$SKILL_DIR/scripts/trade.py" price ethereum-above-on-april-21 YES --threshold 2300
```

## 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `slug` | ✅ | Gamma slug (e.g. `bitcoin-above-on-march-28`) |
| `side` | ✅ | YES/NO/UP/DOWN |
| `金额` | buy必填 / sell可选 | USDC金额，sell默认全部 |
| `--threshold N` | 多market时 | Above盘阈值，如68000 |
| `price` | 可选 | 默认自动定价(MID+1¢买/BID-1¢卖) |

## Slug格式

| 类型 | 格式 | 示例 |
|------|------|------|
| Above盘 | `{coin}-above-on-{month}-{day}` | `bitcoin-above-on-march-28` |
| 涨跌盘 | `{ticker}-up-or-down-on-{month}-{day}-{year}` | `btc-up-or-down-on-march-27-2026` |

## 底层SDK（仅脚本内部使用）

- `py-clob-client-v2@1.0.0` — CLOB V2订单簿 (2026-04-28上线，V1已弃用)
- `py-builder-relayer-client` — Relayer链上操作 (redeem/approve)
- 凭证: `.env.poly` (POLY_PRIVATE_KEY + POLY_PROXY_WALLET + POLY_API_KEY/SECRET/PASSPHRASE)

## V2迁移记录 (2026-05-02)

- OrderArgs 移除 `fee_rate_bps`, V2自动计算
- OrderArgs 移除 `nonce`, V2用 timestamp
- 下单默认 FOK (Fill or Kill)
- Cloudflare 对 `create_or_derive_api_key` 有403干扰，但 fallback 正常
