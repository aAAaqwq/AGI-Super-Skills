# Implementation Guide

Detailed implementation guide for the Arbitrage Opportunity Finder.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     arb_finder.py (CLI)                        │
│         scan | triangular | monitor | calc commands            │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ OpportunityScanner│  │TriangularFinder│  │ProfitCalculator │
│ Direct spread     │  │ Graph-based    │  │ Fee accounting  │
│ detection         │  │ path finding   │  │ Slippage est.   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                    ┌─────────────────┐
                    │  PriceFetcher   │
                    │ Multi-source    │
                    │ aggregation     │
                    └─────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
    ┌─────────┐         ┌─────────┐         ┌─────────┐
    │   CEX   │         │   DEX   │         │Aggregator│
    │ APIs    │         │Subgraphs│         │  APIs   │
    └─────────┘         └─────────┘         └─────────┘
```

---

## Step 1: Configure Data Sources

### Price Fetcher Setup

The `PriceFetcher` class handles multi-source price aggregation:

```python
from price_fetcher import PriceFetcher, ExchangeType

# Initialize with mock data (for simulation)
fetcher = PriceFetcher(use_mock=True)

# Initialize with live data
fetcher = PriceFetcher(
    use_mock=False,
    max_staleness_seconds=30,
)

# Fetch prices from specific exchanges
quotes = fetcher.fetch_all_prices_sync(
    "ETH",
    "USDC",
    exchanges=["binance", "coinbase", "uniswap"],
)
```

### Exchange Configuration

Edit `config/settings.yaml` to enable/disable exchanges:

```yaml
cex:
  binance:
    enabled: true
    maker_fee: 0.0010
    taker_fee: 0.0010
    withdrawal_fee: 0.0005

dex:
  uniswap:
    enabled: true
    fee_tiers: [0.0001, 0.0005, 0.003, 0.01]
    gas_estimate: 150000
```

### API Keys (Optional)

For higher rate limits, configure API keys:

```yaml
data_sources:
  coingecko:
    enabled: true
    api_key: "your-api-key"  # Optional for higher limits
```

---

## Step 2: Opportunity Detection

### Direct Spread Detection

The `OpportunityScanner` finds price differences between exchanges:

```python
from opportunity_scanner import OpportunityScanner

scanner = OpportunityScanner(
    min_profit_pct=0.1,      # 0.1% minimum profit
    gas_price_gwei=30.0,     # Current gas price
    eth_price_usd=2500.0,    # Current ETH price
)

# Scan all exchanges
result = scanner.scan("ETH", "USDC")

# Scan specific exchanges
result = scanner.scan(
    "ETH",
    "USDC",
    exchanges=["binance", "coinbase"],
    exchange_type=ExchangeType.CEX,  # CEX only
)

# Access results
print(f"Found {len(result.opportunities)} opportunities")
if result.best_opportunity:
    print(f"Best: {result.best_opportunity.net_spread_pct}%")
```

### Risk Assessment

Each opportunity includes risk assessment:

```python
from opportunity_scanner import RiskLevel

# Risk factors evaluated:
# - Data staleness (old data = higher risk)
# - Spread size (tiny spreads may disappear)
# - Exchange type (DEX has execution uncertainty)
# - Volume (low volume = higher slippage risk)

for opp in result.opportunities:
    if opp.risk_level == RiskLevel.LOW:
        print(f"Low risk: {opp.buy_exchange} → {opp.sell_exchange}")
```

---

## Step 3: Triangular Arbitrage

### Path Finding Algorithm

The `TriangularFinder` uses graph algorithms to find profitable cycles:

```python
from triangular_finder import TriangularFinder

finder = TriangularFinder(
    fee_rate=Decimal("0.001"),  # Default fee
    min_profit_pct=0.1,        # Minimum to report
)

# Find all triangular opportunities on an exchange
paths = finder.find_opportunities("binance")

# Analyze specific triangle
path = finder.analyze_single_triangle(
    "ETH", "BTC", "USDT",
    exchange="binance",
)
```

### Understanding Path Results

```python
for path in paths:
    print(f"Path: {' → '.join(path.tokens)}")
    print(f"Gross: {path.gross_profit_pct:+.4f}%")
    print(f"Fees: -{path.total_fees_pct:.4f}%")
    print(f"Net: {path.net_profit_pct:+.4f}%")

    if path.is_profitable:
        for step in path.execution_steps:
            print(f"  {step}")
```

---

## Step 4: Profit Calculation

### Detailed Breakdown

The `ProfitCalculator` accounts for all costs:

```python
from profit_calculator import ProfitCalculator
from decimal import Decimal

calc = ProfitCalculator(
    gas_price_gwei=30.0,
    eth_price_usd=2500.0,
    default_slippage_pct=0.1,
)

breakdown = calc.calculate(
    pair="ETH/USDC",
    buy_exchange="binance",
    sell_exchange="coinbase",
    buy_price=Decimal("2541.50"),
    sell_price=Decimal("2543.80"),
    amount=Decimal("10"),  # 10 ETH
)

print(f"Gross Profit: ${breakdown.gross_profit:.2f}")
print(f"Total Costs: ${breakdown.total_costs:.2f}")
print(f"Net Profit: ${breakdown.net_profit:.2f}")
print(f"Profitable: {breakdown.is_profitable}")
```

### Cost Components

```python
# Breakdown includes:
breakdown.buy_fee        # Trading fee on buy exchange
breakdown.sell_fee       # Trading fee on sell exchange
breakdown.withdrawal_fee # Withdrawal from buy exchange
breakdown.gas_cost_usd   # Gas for DEX transactions
breakdown.slippage_cost  # Estimated slippage
breakdown.total_costs    # Sum of all costs
```

### Minimum Trade Size

Calculate minimum profitable trade size:

```python
min_amount = calc.calculate_minimum_amount(
    buy_exchange="binance",
    sell_exchange="coinbase",
    spread_pct=0.1,           # Current spread
    target_profit_usd=Decimal("100"),
)

if min_amount > 0:
    print(f"Need ${min_amount:,.2f} trade for $100 profit")
else:
    print("Spread not profitable at any size")
```

---

## Step 5: Output Formatting

### Console Output

```python
from formatters import ConsoleFormatter

fmt = ConsoleFormatter(width=70)

# Format scan results
print(fmt.format_scan_result(result))

# Format triangular results
print(fmt.format_triangular_results(paths))

# Format profit breakdown
print(fmt.format_profit_breakdown(breakdown))

# Format alert
print(fmt.format_alert(opportunity))
```

### JSON Export

```python
from formatters import JSONFormatter

fmt = JSONFormatter()

# Export as JSON string
json_str = fmt.format_scan_result(result)

# Write to file
with open("results.json", "w") as f:
    f.write(json_str)
```

---

## Step 6: Real-Time Monitoring

### Continuous Scanning

```python
import time

scanner = OpportunityScanner(min_profit_pct=0.1)
formatter = ConsoleFormatter()

threshold = 0.3  # Alert threshold
interval = 5     # Seconds between scans

try:
    while True:
        result = scanner.scan("ETH", "USDC")

        if result.best_opportunity:
            best = result.best_opportunity
            if best.net_spread_pct >= threshold:
                print(formatter.format_alert(best))

        time.sleep(interval)

except KeyboardInterrupt:
    print("Monitoring stopped")
```

### Alert Integration

Extend the monitoring loop to send alerts:

```python
def send_alert(opportunity):
    """Send alert via your preferred method."""
    # Discord webhook, Telegram, email, etc.
    pass

# In monitoring loop:
if best.net_spread_pct >= threshold:
    print(formatter.format_alert(best))
    send_alert(best)
```

---

## Directory Structure

```
skills/finding-arbitrage-opportunities/
├── SKILL.md                    # Core skill instructions
├── PRD.md                      # Product requirements
├── ARD.md                      # Architecture requirements
├── scripts/
│   ├── arb_finder.py           # Main CLI entry point
│   ├── price_fetcher.py        # Multi-source price aggregation
│   ├── opportunity_scanner.py  # Direct spread detection
│   ├── triangular_finder.py    # Graph-based path finding
│   ├── profit_calculator.py    # Fee-aware profit calculation
│   └── formatters.py           # Output formatting
├── config/
│   └── settings.yaml           # Configuration options
└── references/
    ├── errors.md               # Error handling guide
    ├── examples.md             # Usage examples
    └── implementation.md       # This file
```

---

## Dependencies

### Python Packages

```
# No external packages required for core functionality
# Scripts use mock data for demonstration

# Optional for live data:
# aiohttp>=3.9.0      # Async HTTP for parallel fetches
# websockets>=12.0    # Real-time exchange feeds
```

### External Services (Optional)

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| CoinGecko | Price aggregation | 10 calls/min |
| The Graph | DEX subgraphs | 100K queries/month |
| Exchange APIs | Direct prices | Varies |

---

## Performance Considerations

### Rate Limiting

```python
# Configure in settings.yaml
scanning:
  request_delay_ms: 100      # Delay between requests
  backoff_multiplier: 2.0    # Exponential backoff
  max_retries: 3             # Retry attempts
```

### Data Freshness

```python
# Reject stale data
max_staleness: 30  # seconds

# Stale data flagged in risk assessment
if quote.age_seconds > 30:
    opportunity.risk_level = RiskLevel.HIGH
```

### Parallel Fetching

For live implementations, fetch prices concurrently:

```python
import asyncio

async def fetch_all_parallel(pairs, exchanges):
    tasks = [
        fetch_price(pair, exchange)
        for pair in pairs
        for exchange in exchanges
    ]
    return await asyncio.gather(*tasks)
```

---

## Educational Disclaimer

This tool is for **analysis and learning purposes only**.

**Risks of actual arbitrage trading:**
- Opportunities disappear in milliseconds
- Price data may be delayed or inaccurate
- Transaction costs can exceed profits
- Exchange withdrawals may be slow
- Markets are highly competitive

**Always verify** data independently before making any trading decisions.
