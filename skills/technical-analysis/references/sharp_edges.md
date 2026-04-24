# Technical Analysis - Sharp Edges

## You Only See Patterns That Worked

### **Id**
survivorship-bias-patterns
### **Severity**
CRITICAL
### **Description**
Charts shared on social media show successful patterns, not the failures
### **Symptoms**
  - Pattern win rate seems higher than reality
  - Frustration when "perfect" patterns fail
  - Overconfidence in pattern recognition
### **Detection Pattern**
pattern.*100%|always.*works|never.*fails
### **Solution**
  Reality Check by Pattern (Bulkowski's Encyclopedia):
  
  | Pattern           | Success Rate | Avg Move |
  |-------------------|--------------|----------|
  | Head & Shoulders  | 63%          | 16%      |
  | Double Bottom     | 65%          | 18%      |
  | Cup & Handle      | 65%          | 20%      |
  | Bull Flag         | 63%          | 15%      |
  | Triangle (sym)    | 54%          | 12%      |
  
  Key Insight: Even "reliable" patterns fail 35-45% of the time.
  
  Action Items:
  1. Study failed patterns as much as successful ones
  2. Always use stop losses assuming failure
  3. Size positions for the failure rate, not success rate
  4. Backtest on your own data, don't trust screenshots
  
### **References**
  - "Encyclopedia of Chart Patterns" - Thomas Bulkowski

## All Indicators Lag - You're Trading the Past

### **Id**
indicator-lag-trap
### **Severity**
CRITICAL
### **Description**
Indicators are derived from past prices, they don't predict future
### **Symptoms**
  - Entering trades late after moves already happened
  - Stop losses hit by retracements
  - Why did it reverse right after my signal?
### **Detection Pattern**
indicator.*predict|signal.*before
### **Solution**
  Indicator Reality:
  
  Moving Averages: Most lagging (smooth past data)
  - 200 MA: ~100 days of lag
  - 50 MA: ~25 days of lag
  
  MACD: Lagging (MA of MAs)
  - Signal line crossover is already 5-10 bars old
  
  RSI: Less lag but still reactive
  - Measures past momentum, not future
  
  Better Approach:
  1. Use indicators for CONTEXT, not signals
     - '"We''re in uptrend" not "buy now"'
  
  2. Lead with price action
     - Price structure changes before indicators
  
  3. Use indicators to FILTER, not TRIGGER
     - Only take price action longs when RSI > 50
  
  4. Anticipate indicator signals
     - When RSI approaching 30 + support, prepare
     - Don't wait for indicator to confirm
  
### **References**
  - https://www.investopedia.com/terms/l/laggingindicator.asp

## Divergence Can Persist Far Longer Than Your Account

### **Id**
divergence-persistence
### **Severity**
CRITICAL
### **Description**
RSI/MACD divergence is not a timing tool - trends continue despite divergence
### **Symptoms**
  - Multiple losing trades betting on divergence
  - "Divergence doesn't work anymore"
  - Account drawdown from fading strong trends
### **Detection Pattern**
divergence.*reversal|divergence.*signal
### **Solution**
  Divergence Reality:
  - Divergence shows slowing momentum, NOT reversal
  - Trends can make 5-10 divergences before reversing
  - In 2021 BTC: Divergence from $30k, didn't reverse until $69k
  
  Rules for Divergence:
  1. NEVER trade divergence alone
     - Requires structure break confirmation
  
  2. Divergence is context, not signal
     - '"Momentum weakening" not "reversal imminent"'
  
  3. Only trade divergence at key levels
     - Major support/resistance
     - Key Fibonacci levels
     - Previous swing highs/lows
  
  4. Wait for price confirmation
     - Bullish div + break above prior high = valid
     - Bullish div alone = early and dangerous
  
  Safer Divergence System:
  - Divergence appears: Alert, don't trade
  - Price breaks structure: Prepare
  - Retest of break point: Enter with stop
  
### **References**
  - Countless blown accounts trading divergence in trends

## Support/Resistance Are Zones, Not Exact Prices

### **Id**
support-resistance-precision
### **Severity**
HIGH
### **Description**
S/R levels are probability zones, not magic lines where price reverses
### **Symptoms**
  - Stop losses hit by "wicks through support"
  - Missing entries waiting for exact level
  - Frustration when price goes "through" level
### **Detection Pattern**
exact.*support|precise.*resistance|touch.*level
### **Solution**
  S/R Zone Reality:
  
  Why Levels Are Zones:
  - Different traders draw levels differently
  - Orders cluster around area, not single price
  - Liquidity hunters run stops beyond levels
  
  Better Approach:
  1. Draw zones, not lines
     - Support ZONE from $45,000-$45,500
     - Not "support at $45,250"
  
  2. Wait for reaction, not touch
     - Price enters zone = watch
     - Price reacts with volume = signal
     - Price acceptance in zone = level broken
  
  3. Place stops beyond zones
     - If zone is $45,000-$45,500
     - Stop below $44,800 (below zone + buffer)
  
  4. Enter in zones, not at edges
     - Scale in as price moves through zone
     - Average entry in middle of zone
  
  Zone Width Guidelines:
  - Crypto: 1-3% price range
  - Forex: 20-50 pips
  - Stocks: Depends on ATR
  
### **References**
  - Al Brooks price action methodology

## Different Timeframes Give Conflicting Signals

### **Id**
multiple-timeframe-conflict
### **Severity**
HIGH
### **Description**
1H says buy, 4H says sell, daily says hold - analysis paralysis
### **Symptoms**
  - Confusion about which timeframe to follow
  - Missed trades due to conflicting signals
  - Taking signals against higher timeframe trend
### **Detection Pattern**
timeframe.*conflict|which.*timeframe
### **Solution**
  Timeframe Hierarchy (Higher TF Dominates):
  
  Structure:
  - Position trading: Weekly → Daily → 4H
  - Swing trading: Daily → 4H → 1H
  - Day trading: 4H → 1H → 15M
  - Scalping: 1H → 15M → 5M
  
  Rules:
  1. NEVER trade against two-higher timeframe
     - If Weekly bearish, don't go long
     - Period.
  
  2. Higher TF = Trend direction
     - '"What''s the path of least resistance?"'
  
  3. Middle TF = Setup identification
     - '"Where''s the opportunity?"'
  
  4. Lower TF = Entry timing
     - '"When exactly do I click?"'
  
  Conflict Resolution:
  - Higher TF bullish + Lower TF bearish = Wait
  - Higher TF bearish + Lower TF bullish = Short setup
  - All aligned = High conviction trade
  
### **References**
  - Multiple timeframe analysis best practices

## Patterns Are Obvious in Hindsight, Ambiguous in Real-Time

### **Id**
hindsight-pattern-clarity
### **Severity**
HIGH
### **Description**
Easy to see patterns on historical charts, hard to identify live
### **Symptoms**
  - "Why didn't I see that head and shoulders forming?"
  - Patterns only clear after completion
  - Analysis paralysis on live charts
### **Detection Pattern**
obvious|clearly.*forming|should.*have.*seen
### **Solution**
  Hindsight Bias Reality:
  
  In hindsight: "Clear head and shoulders pattern"
  In real-time: "Is this a head? Or continuation? Or just noise?"
  
  Solutions:
  1. Trade the completion, not the formation
     - H&S: Trade neckline break, not head
     - Triangle: Trade breakout, not anticipation
  
  2. Define pattern BEFORE it completes
     - '"If price does X, pattern confirmed"'
     - '"If price does Y, pattern invalidated"'
     - Write it down in advance
  
  3. Accept ambiguity as normal
     - Not every pattern resolves cleanly
     - Skip unclear setups
  
  4. Use partial positions
     - 50% on pattern setup
     - 50% on confirmation
  
  5. Trade what you see, not what you think
     - Price above key level = bullish
     - Price below key level = bearish
     - Everything else = unclear, wait
  
### **References**
  - Common trading psychology research

## High Volume Doesn't Always Confirm - Context Matters

### **Id**
volume-interpretation-errors
### **Severity**
HIGH
### **Description**
Volume meaning depends on price action, not just volume level
### **Symptoms**
  - Buying breakouts that fail despite "high volume"
  - Missing reversals because "volume was low"
  - Misreading climactic volume events
### **Detection Pattern**
high.*volume.*confirm|volume.*breakout
### **Solution**
  Volume Contexts:
  
  1. High Volume + Breakout Success
     - Strong institutions driving move
     - Follow the move
  
  2. High Volume + Failed Breakout
     - Climactic exhaustion
     - Often reversal setup
     - VERY BEARISH despite high volume
  
  3. Low Volume + Breakout
     - Lack of participation
     - Likely failure or slow development
  
  4. Low Volume + Pullback in Trend
     - Healthy consolidation
     - Continuation likely
  
  5. Climactic Volume + Reversal Candle
     - Selling/buying exhaustion
     - High probability reversal zone
  
  Better Volume Rules:
  - Breakout volume should be 1.5x+ average
  - If breakout fails on high volume = bearish
  - Declining volume in correction = healthy
  - Rising volume in correction = concerning
  
### **References**
  - Wyckoff volume analysis principles

## Your Optimized System Won't Work in Live Trading

### **Id**
optimization-overfitting
### **Severity**
HIGH
### **Description**
Backtesting optimization finds parameters that fit past noise, not future edge
### **Symptoms**
  - Amazing backtest results, terrible live results
  - System works for one asset but not others
  - Frequent parameter changes "to adapt"
### **Detection Pattern**
optimiz|best.*parameter|backtest.*profit
### **Solution**
  Overfitting Signs:
  - Many parameters (more = more overfitting)
  - Specific values (RSI 23 vs RSI 20)
  - Works on one asset only
  - Sharp equity curve changes at specific dates
  
  Anti-Overfitting Rules:
  1. Use standard parameters
     - RSI 14, MACD 12/26/9
     - If edge requires specific params, edge is weak
  
  2. Out-of-sample testing
     - Optimize on 2019-2021
     - Test on 2022-2023
     - If it fails, no edge
  
  3. Walk-forward analysis
     - Optimize on period 1, test on period 2
     - Optimize on period 2, test on period 3
     - Continuous validation
  
  4. Cross-asset testing
     - Works on BTC? Try ETH, SPY, Gold
     - Real edge transfers across markets
  
  5. Fewer is better
     - 2-3 parameters max
     - Simple systems are robust systems
  
### **References**
  - "Advances in Financial Machine Learning" - Marcos Lopez de Prado

## Technical Analysis Fails at News Events

### **Id**
news-event-technical-conflict
### **Severity**
MEDIUM
### **Description**
Charts don't predict FOMC, earnings, or black swans
### **Symptoms**
  - "Perfect setup" destroyed by news
  - Large gap moves invalidate analysis
  - Stop losses gapped through
### **Detection Pattern**
FOMC|earnings|news.*event|gap
### **Solution**
  News Event Protocol:
  
  High-Impact Events:
  - FOMC (8x/year)
  - NFP (monthly)
  - CPI/PPI (monthly)
  - Earnings (quarterly)
  - Unexpected: War, pandemic, political
  
  Rules:
  1. No new positions 24-48h before major events
     - Technical analysis = probability
     - News = binary unpredictable outcome
  
  2. Reduce position size if holding through
     - Max 50% normal size
     - Use options for defined risk
  
  3. Let dust settle after news
     - Wait 1-2 hours after release
     - Let algorithms stop firing
     - Then analyze new structure
  
  4. Use news as invalidation, not signal
     - If bullish setup + bearish news = wait
     - Don't fight narrative even if chart says buy
  
### **References**
  - Risk management best practices

## Patterns Transform into Different Patterns

### **Id**
pattern-morphing
### **Severity**
MEDIUM
### **Description**
That "bull flag" might become a "descending channel" if it fails
### **Symptoms**
  - Holding losing trades hoping pattern completes
  - Rationalizing why pattern is still valid
  - Pattern changes name 3 times before completion
### **Detection Pattern**
still.*valid|pattern.*developing
### **Solution**
  Pattern Evolution Reality:
  
  Bull flag → Descending channel → Bearish breakdown
  Cup & handle → Failed breakout → M top
  H&S → Failed neckline → Continuation
  
  Solution: Pre-Define Invalidation
  
  Before Entry:
  - "This is a bull flag"
  - "Invalid if: closes below $X"
  - "Valid if: breaks above $Y with volume"
  
  After Entry:
  - Pattern invalidated? Exit. Don't rename.
  - Don't let bull flag become "accumulation"
  - Don't let M top become "complex bottom"
  
  Rule: If you have to rename pattern to stay in trade,
  you're rationalizing a loss. Exit.
  
### **References**
  - Common pattern failure analysis

## Complex Indicator Systems Don't Outperform Simple Ones

### **Id**
indicator-combo-complexity
### **Severity**
MEDIUM
### **Description**
Adding more indicators adds complexity without adding edge
### **Symptoms**
  - Conflicting signals from many indicators
  - Analysis takes too long
  - I need all 5 indicators to agree
### **Detection Pattern**
5.*indicators|multiple.*confirm
### **Solution**
  Complexity Curve:
  
  Indicators: 1 → Edge improves
  Indicators: 2-3 → Marginally better
  Indicators: 4+ → No improvement, more confusion
  
  Studies show:
  - Adding indicators beyond 2-3 doesn't improve returns
  - Simple systems are more robust
  - Complex systems overfit
  
  Minimalist Approach:
  1. One trend indicator (MA or price structure)
  2. One momentum indicator (RSI or MACD)
  3. Volume (not an oscillator)
  
  That's it. Three things max.
  
  If your system needs 7 confirmations:
  - You're not confident in any of them
  - Simplify until you trust 1-2 things
  
### **References**
  - Trading system research literature