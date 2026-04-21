# Signal Classification Rules

## Sentiment Analysis Keywords

### 🔴 DANGER Keywords (Bearish)
- "hawkish", "rate hike", "higher for longer", "inflation rises"
- "war escalates", "military conflict", "sanctions"
- "hack", "exploit", "flash crash", "bankrupt", "insolvent"
- "SEC charges", "regulatory crackdown", "ban", "illegal"
- "recession", "slowdown", "contraction", "crisis"
- "sell-off", "bloodbath", "capitulation", "plunge"
- "hash rate drops", "miner capitulation"
- "whale dumps", "large transfer to exchange"

### 🟢 OPPORTUNITY Keywords (Bullish)
- "dovish", "rate cut", "easing", "stimulus"
- "war de-escalates", "ceasefire", "peace talks"
- "ETF approved", "inflow record", "institutional adoption"
- "regulatory clarity", "pro-crypto", "legalized"
- "breakout", "ATH", "rally", "surge"
- "partnership with", "adopted by", "integration"
- "hash rate ATH", "miner accumulation"

### 🟡 CAUTION Keywords (Uncertain)
- "Fed meeting", "CPI release", "PPI data", "NFP"
- "awaiting", "pending", "uncertain"
- "mixed signals", "divergent", "volatile"
- "resistance", "support test", "consolidation"

## Impact Scoring

Each signal gets an impact score (1-10):

| Score | Impact | Action |
|-------|--------|--------|
| 1-3 | Low | NEUTRAL, log only |
| 4-5 | Moderate | CAUTION if no other signals |
| 6-7 | High | CAUTION |
| 8-10 | Critical | DANGER |

### Multiplier Rules
- **Fed-related**: ×1.5 (Fed moves always amplified)
- **Geopolitical**: ×1.3 (war/news amplifies moves)
- **Multiple signals same direction**: ×1.2 per additional signal
- **During existing CAUTION**: ×1.3 (risks compound)

### Example Scoring
- "Powell says inflation persistent" → base:7 × Fed:1.5 = 10.5 → DANGER
- "CPI above expected" → base:5 × Fed:1.5 = 7.5 → CAUTION→DANGER
- "Iran launches new attack" → base:8 × Geo:1.3 = 10.4 → DANGER
- "Bitcoin ETF sees $500M inflow" → base:4 → CAUTION (positive direction)
