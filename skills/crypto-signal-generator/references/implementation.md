# Implementation Guide

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Fetch    │────▶│   Indicators    │────▶│   Signal Gen    │
│   (yfinance)    │     │   (7 types)     │     │   (composite)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │   Risk Mgmt     │
                                                │   (SL/TP/RR)    │
                                                └─────────────────┘
```

## Step 1: Install Dependencies

```bash
pip install yfinance pandas numpy matplotlib
```

## Step 2: Single Symbol Analysis

```bash
cd scripts/

# Quick signal check
python scanner.py --symbols BTC-USD

# Detailed breakdown
python scanner.py --symbols BTC-USD --detail
```

## Step 3: Multi-Symbol Scanning

```bash
# Predefined watchlists
python scanner.py --watchlist crypto_top10
python scanner.py --watchlist crypto_defi

# Custom symbols
python scanner.py --symbols BTC-USD,ETH-USD,SOL-USD,AVAX-USD
```

## Step 4: Filter and Rank

```bash
# Only actionable signals (buy/sell with 60%+ confidence)
python scanner.py --filter buy --min-confidence 60

# Rank by most bearish for short opportunities
python scanner.py --rank bearish
```

## Step 5: Export Results

```bash
python scanner.py --output results/signals_$(date +%Y%m%d).json
```

## Indicator Calculations

### RSI (Relative Strength Index)

```python
RSI = 100 - (100 / (1 + RS))
RS = Average Gain / Average Loss over period
```

- Period: 14 (default)
- Oversold: < 30 (BUY signal)
- Overbought: > 70 (SELL signal)

### MACD

```python
MACD Line = EMA(12) - EMA(26)
Signal Line = EMA(9) of MACD Line
Histogram = MACD Line - Signal Line
```

- Bullish: MACD crosses above signal
- Bearish: MACD crosses below signal

### Bollinger Bands

```python
Middle Band = SMA(20)
Upper Band = Middle + 2 * StdDev
Lower Band = Middle - 2 * StdDev
%B = (Price - Lower) / (Upper - Lower)
```

- Oversold: %B < 0 (price below lower band)
- Overbought: %B > 1 (price above upper band)

### ADX (Average Directional Index)

```python
ADX = Moving Average of DX
DX = |+DI - -DI| / |+DI + -DI| * 100
```

- < 20: No trend
- 20-40: Developing trend
- > 40: Strong trend
- +DI > -DI: Uptrend
- -DI > +DI: Downtrend

## Signal Weighting

Default weights:

| Indicator | Weight | Rationale |
|-----------|--------|-----------|
| RSI | 1.0 | Primary momentum |
| MACD | 1.0 | Trend + momentum |
| Bollinger | 1.0 | Mean reversion |
| Trend | 1.0 | Long-term direction |
| Volume | 0.5 | Confirmation only |
| Stochastic | 0.5 | Redundant with RSI |
| ADX | 0.5 | Trend strength filter |

Composite score = Weighted average of all signals (-2 to +2)

## Confidence Calculation

```python
agreement = 1 - (std(component_scores) / 2)  # 0 to 1
strength = abs(composite_score) / 2          # 0 to 1
confidence = (agreement * 0.5 + strength * 0.5) * 100
```

High confidence when:
- All indicators agree (low standard deviation)
- Signals are extreme (strong readings)

## Risk Management

Stop-loss and take-profit based on ATR:

```python
ATR = Average True Range (14 periods)

# For BUY signals:
Stop Loss = Entry - (ATR * 2.0)
Take Profit = Entry + (ATR * 2.0 * Risk_Reward)

# For SELL signals:
Stop Loss = Entry + (ATR * 2.0)
Take Profit = Entry - (ATR * 2.0 * Risk_Reward)
```

Default: 2:1 risk/reward ratio

## Customization

### Adjust Indicator Parameters

Edit `config/settings.yaml`:

```yaml
indicators:
  rsi:
    period: 14       # Shorter = more signals
    overbought: 75   # Higher = fewer sell signals
    oversold: 25     # Lower = fewer buy signals
```

### Adjust Signal Weights

Emphasize certain indicators:

```yaml
signals:
  weights:
    rsi: 2.0         # Double RSI weight
    macd: 1.0
    trend: 0.5       # Reduce trend weight
```

### Custom Watchlists

Add in `config/settings.yaml`:

```yaml
watchlists:
  my_portfolio:
    - BTC-USD
    - ETH-USD
    - AAPL
    - GOOGL
```

## Programmatic Usage

```python
from indicators import calculate_all_indicators
from signals import SignalGenerator, format_signal
import yfinance as yf

# Fetch data
df = yf.Ticker('BTC-USD').history(period='6mo', interval='1d')
df.columns = [c.lower() for c in df.columns]

# Calculate indicators
df = calculate_all_indicators(df)

# Generate signal
generator = SignalGenerator()
signal = generator.generate_signal(df, 'BTC-USD')

# Display
print(format_signal(signal))

# Access components
for comp in signal.components:
    print(f"{comp.name}: {comp.signal.value} - {comp.reasoning}")
```

## Integration Tips

### With Backtester

```bash
# 1. Get current signal
python scanner.py --symbols BTC-USD --output current_signal.json

# 2. Identify dominant indicator
cat current_signal.json | jq '.signals[0].components | sort_by(.weight) | reverse | .[0]'

# 3. Backtest that strategy
python ../trading-strategy-backtester/.../backtest.py --strategy rsi_reversal
```

### Automated Scanning

Create a cron job:

```bash
# Every 4 hours during trading hours
0 */4 * * * cd /path/to/scripts && python scanner.py --watchlist crypto_top10 --min-confidence 70 --output ~/signals/$(date +\%Y\%m\%d_\%H).json
```
