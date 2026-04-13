# Polymarket SDK API Test Results

Date: 2026-02-25

## Environment
- Python 3.12, py-clob-client 0.34.6
- Chain: Polygon (137)
- Host: https://clob.polymarket.com
- Private key: loaded from `pass show api/polymarket-wallet` (66 chars)

## Test Results

| API | Status | Notes |
|-----|--------|-------|
| Gamma API (markets) | ✅ OK | HTTP 200, returns market data with volume |
| CLOB create_or_derive_api_creds | ✅ OK | Successfully derived API credentials |
| CLOB get_markets | ✅ OK | Returns 1000 markets per page with cursor pagination |
| CLOB get_order_book | ⚠️ Partial | 404 on some tokens (no orderbook for that market), expected behavior |
| CLOB create_order (build only) | ✅ OK | SignedOrder built with order + signature, signing works |
| CLOB get_orders | ✅ OK | Returns list (empty = no open orders) |
| CLOB get_trades | ✅ OK | Returns list (empty = no trade history) |

## Summary
- All core APIs functional
- Wallet credentials valid and signing works
- Ready for integration into trading wrapper

## ⚠️ Security Note
Private key was exposed in Telegram on 2026-02-20. Do not store significant funds in this wallet.
