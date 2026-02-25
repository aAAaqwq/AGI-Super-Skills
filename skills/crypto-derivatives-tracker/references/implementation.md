# Implementation Guide

## Architecture Overview

The crypto derivatives tracker uses a modular architecture with specialized analyzers for each derivatives metric type.

```
┌─────────────────────────────────────────────────────────────────┐
│                     derivatives_tracker.py                       │
│                       (Main CLI Entry)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│FundingTracker │   │  OIAnalyzer   │   │Liquidation    │
│               │   │               │   │   Monitor     │
└───────────────┘   └───────────────┘   └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ExchangeClient                               │
│                  (Unified Data Layer)                            │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────┬───────┴───────┬─────────────┐
        ▼             ▼               ▼             ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ Binance │   │  Bybit  │   │   OKX   │   │ Deribit │
   └─────────┘   └─────────┘   └─────────┘   └─────────┘
```

## Step 1: Exchange Client Setup

The ExchangeClient provides a unified interface for all exchanges.

### Configuration

Set up API credentials in environment variables or config file:

```python
# Environment-based configuration
import os

config = {
    "binance": {
        "api_key": os.getenv("BINANCE_API_KEY"),
        "api_secret": os.getenv("BINANCE_API_SECRET"),
        "base_url": "https://fapi.binance.com",
    },
    "bybit": {
        "api_key": os.getenv("BYBIT_API_KEY"),
        "api_secret": os.getenv("BYBIT_API_SECRET"),
        "base_url": "https://api.bybit.com",
    },
    "okx": {
        "api_key": os.getenv("OKX_API_KEY"),
        "api_secret": os.getenv("OKX_API_SECRET"),
        "passphrase": os.getenv("OKX_PASSPHRASE"),
        "base_url": "https://www.okx.com",
    },
    "deribit": {
        "client_id": os.getenv("DERIBIT_CLIENT_ID"),
        "client_secret": os.getenv("DERIBIT_CLIENT_SECRET"),
        "base_url": "https://www.deribit.com",
    },
}
```

### Mock Mode

For development and testing, use mock mode:

```python
from exchange_client import ExchangeClient

# Use mock data (no API calls)
client = ExchangeClient(use_mock=True)

# Use live data
client = ExchangeClient(use_mock=False)
```

## Step 2: Funding Rate Tracking

### Data Collection

Funding rates are collected every 8 hours on most exchanges:

```python
from funding_tracker import FundingTracker

tracker = FundingTracker()

# Get current funding rates
analysis = tracker.analyze("BTC")

# Access individual exchange rates
for rate in analysis.rates:
    print(f"{rate.exchange}: {rate.rate:.4%} (next: {rate.time_to_payment_str})")
```

### Interpretation Thresholds

| Rate Range | Interpretation | Action |
|------------|----------------|--------|
| > 0.08% | Extreme Bullish | Contrarian short opportunity |
| 0.03-0.08% | Strong Bullish | Market overheated |
| 0.005-0.03% | Moderate Bullish | Normal uptrend |
| -0.005-0.005% | Neutral | Balanced positioning |
| -0.03-(-0.005)% | Moderate Bearish | Normal downtrend |
| < -0.03% | Strong Bearish | Contrarian long opportunity |

### Arbitrage Detection

```python
# Find funding rate discrepancies between exchanges
opportunities = tracker.get_arbitrage_opportunities(
    symbols=["BTC", "ETH"],
    min_spread=0.02  # 0.02% minimum spread
)
```

## Step 3: Open Interest Analysis

### Data Aggregation

OI is aggregated across exchanges with weighted calculations:

```python
from oi_analyzer import OIAnalyzer

analyzer = OIAnalyzer()
analysis = analyzer.analyze("BTC")

# Weighted average change (by OI size)
print(f"24h Change: {analysis.avg_change_24h}%")

# Market structure
print(f"Trend: {analysis.trend} ({analysis.trend_strength})")
```

### Divergence Detection

Classic OI/Price divergence patterns:

| OI Direction | Price Direction | Signal | Interpretation |
|--------------|-----------------|--------|----------------|
| Up | Up | Bullish | New longs entering, trend confirmed |
| Up | Down | Bearish | New shorts entering, trend confirmed |
| Down | Up | Short Squeeze | Shorts covering, rally may be weak |
| Down | Down | Long Liquidation | Longs closing, selloff may find support |

```python
divergence = analyzer.detect_divergence("BTC", price_change_24h=3.5)
if divergence:
    print(f"Signal: {divergence.signal}")
    print(f"Confidence: {divergence.confidence}")
```

## Step 4: Liquidation Monitoring

### Level Calculation

Liquidation levels are estimated based on:
- Open positions at each exchange
- Average leverage used
- Maintenance margin requirements

```python
from liquidation_monitor import LiquidationMonitor

monitor = LiquidationMonitor()
summary = monitor.get_summary("BTC", current_price=Decimal("67500"))

# Cascade risk assessment
print(f"Risk: {summary.cascade_risk}")  # low, medium, high, critical
```

### Cascade Risk Thresholds

| Risk Level | Liquidations Within 5% | Description |
|------------|------------------------|-------------|
| Critical | > $500M | High probability of cascade |
| High | $200-500M | Elevated risk |
| Medium | $100-200M | Moderate risk |
| Low | < $100M | Normal conditions |

### Heatmap Generation

```python
# Get structured data for visualization
heatmap = monitor.generate_heatmap_data(
    symbol="BTC",
    current_price=Decimal("67500"),
    levels=5  # 5 levels above and below
)
```

## Step 5: Options Analysis

### IV Interpretation

Implied volatility is compared to historical ranges:

```python
from options_analyzer import OptionsAnalyzer

analyzer = OptionsAnalyzer()
analysis = analyzer.analyze("BTC")

# IV interpretation
if analysis.iv_interpretation == "high":
    print("IV elevated - consider selling premium")
elif analysis.iv_interpretation == "low":
    print("IV compressed - consider buying premium")
```

### Put/Call Ratio

| PCR Range | Interpretation |
|-----------|----------------|
| > 1.2 | Bearish (more puts than calls) |
| 0.7-1.2 | Neutral |
| < 0.7 | Bullish (more calls than puts) |

### Max Pain Calculation

Max pain is the strike price where options writers have minimum payout:

```python
levels = analyzer.get_max_pain_levels("BTC")
for level in levels:
    print(f"{level['expiry']}: ${level['max_pain']:,.0f}")
```

## Step 6: Basis Calculations

### Term Structure Analysis

```python
from basis_calculator import BasisCalculator

calc = BasisCalculator()
analysis = calc.analyze("BTC", spot_price=Decimal("67500"))

# Market structure
print(f"Structure: {analysis.market_structure}")  # contango or backwardation
```

### Carry Trade Identification

```python
opportunities = calc.find_carry_opportunities(
    symbols=["BTC", "ETH"],
    min_yield=5.0  # Minimum 5% annualized
)

for opp in opportunities:
    print(f"{opp.symbol}: {opp.annualized_yield:.1f}% yield")
    print(f"  Strategy: {opp.strategy}")
```

## Step 7: Report Generation

### Console Output

```python
from formatters import ConsoleFormatter

console = ConsoleFormatter(width=70)

# Create headers and sections
print(console.header("BTC DERIVATIVES"))
print(console.section("FUNDING RATES"))
```

### JSON Export

```python
from formatters import JSONFormatter

json_fmt = JSONFormatter(indent=2)

# Export analysis results
report = json_fmt.derivatives_dashboard(
    symbol="BTC",
    funding=funding_data,
    oi=oi_data,
    liquidations=liq_data
)

# Write to file
with open("report.json", "w") as f:
    f.write(report)
```

## Performance Considerations

### Caching

Cache static data that doesn't change frequently:

```python
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=100)
def get_max_pain_cached(symbol, expiry):
    # Only recalculate every 15 minutes
    cache_key = (symbol, expiry, datetime.now().strftime("%Y%m%d%H%M")[:11])
    return calculate_max_pain(symbol, expiry)
```

### Rate Limiting

Implement proper rate limiting for API calls:

```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, calls_per_minute=60):
        self.calls_per_minute = calls_per_minute
        self.calls = defaultdict(list)

    def wait_if_needed(self, exchange):
        now = time.time()
        minute_ago = now - 60

        # Clean old calls
        self.calls[exchange] = [
            t for t in self.calls[exchange] if t > minute_ago
        ]

        if len(self.calls[exchange]) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[exchange][0])
            time.sleep(sleep_time)

        self.calls[exchange].append(now)
```

### Parallel Fetching

Fetch from multiple exchanges in parallel:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def fetch_all_funding(symbols):
    with ThreadPoolExecutor(max_workers=5) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, fetch_funding, symbol)
            for symbol in symbols
        ]
        return await asyncio.gather(*tasks)
```

## Testing

### Unit Tests

```python
def test_funding_sentiment():
    tracker = FundingTracker()

    # High positive funding should be bullish
    sentiment, strength = tracker._analyze_sentiment(0.05)
    assert sentiment == "bullish"
    assert strength == "strong"

    # Negative funding should be bearish
    sentiment, strength = tracker._analyze_sentiment(-0.03)
    assert sentiment == "bearish"
```

### Mock Testing

```python
def test_with_mock_data():
    client = ExchangeClient(use_mock=True)
    tracker = FundingTracker(client=client)

    analysis = tracker.analyze("BTC")
    assert analysis.weighted_avg is not None
    assert len(analysis.rates) > 0
```

## Deployment

### Environment Variables

Required for production:

```bash
# Exchange API Keys
export BINANCE_API_KEY="your-key"
export BINANCE_API_SECRET="your-secret"
export BYBIT_API_KEY="your-key"
export BYBIT_API_SECRET="your-secret"

# Optional: Deribit for options data
export DERIBIT_CLIENT_ID="your-id"
export DERIBIT_CLIENT_SECRET="your-secret"
```

### Running the CLI

```bash
# Install dependencies
pip install -r requirements.txt

# Run analysis
python derivatives_tracker.py funding BTC
python derivatives_tracker.py dashboard BTC ETH SOL --format json
```

### Scheduling

For continuous monitoring, schedule regular runs:

```bash
# Cron job every 15 minutes
*/15 * * * * cd /path/to/skill && python derivatives_tracker.py dashboard BTC ETH >> /var/log/derivatives.log 2>&1
```
