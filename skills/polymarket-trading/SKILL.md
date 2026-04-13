# Polymarket CLOB Trader

Direct CLOB API trading client for Polymarket with backtesting research.

## Features
- Market data retrieval and order book access
- Buy/sell order placement via CLOB
- Kelly criterion backtesting strategies
- API integration test results

## Files
```
clob_trader.py              # Main trading client
research/
├── backtest_kelly_v2.py    # Kelly criterion v2 backtest
├── backtest_kelly_strategy.py  # Kelly strategy backtest
├── kelly_backtest.py       # Original Kelly backtest
└── strategy-ideas.md       # Strategy brainstorming notes
api-test-results.md         # API endpoint test results
```
