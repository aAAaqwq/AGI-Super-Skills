# Technical Analysis

## Patterns


---
  #### **Name**
Wyckoff Accumulation
  #### **Description**
Institutional accumulation pattern before markup phase
  #### **When**
Looking for major trend reversals at lows after extended decline
  #### **Why It Works**
Composite operators (institutions) accumulate shares over time, creating recognizable phases
  #### **Example**
    Wyckoff Accumulation Phases:
    
    Phase A: Stopping the downtrend
    - PS (Preliminary Support): First support after decline
    - SC (Selling Climax): High volume panic low
    - AR (Automatic Rally): Sharp bounce from SC
    - ST (Secondary Test): Test of SC on lower volume
    
    Phase B: Building the cause
    - Trading range between AR and SC
    - Multiple ST's, shakeouts, upthrusts
    - Volume decreases as weak hands exit
    
    Phase C: Test (Spring)
    - Price breaks below SC briefly
    - Low volume = lack of selling
    - Shakeout of remaining weak hands
    
    Phase D: Markup begins
    - SOS (Sign of Strength): Rally on increasing volume
    - LPS (Last Point of Support): Higher low retest
    
    Phase E: Markup
    - Price leaves range, trends up
    
    # Detection code
    def detect_spring(df, lookback=50):
        """Detect potential Wyckoff spring (Phase C)"""
        recent_low = df['low'].rolling(lookback).min()
    
        # Spring: price briefly breaks low, then closes above
        spring = (
            (df['low'] < recent_low.shift(1)) &  # Break below prior low
            (df['close'] > recent_low.shift(1)) &  # Close back above
            (df['volume'] < df['volume'].rolling(20).mean())  # Low volume
        )
        return spring
    
  #### **Success Rate**
~65-70% when properly identified with volume confirmation

---
  #### **Name**
Volume Profile Value Area
  #### **Description**
Using volume distribution to identify high-probability support/resistance
  #### **When**
Identifying where price is likely to find acceptance or rejection
  #### **Why It Works**
Price spends most time at prices where most volume traded (fair value)
  #### **Example**
    Volume Profile Components:
    
    POC (Point of Control): Price with highest volume
    - Acts as magnet for price
    - Strong S/R when tested from outside
    
    Value Area (VA): 70% of volume distribution
    - VAH (Value Area High): Upper bound
    - VAL (Value Area Low): Lower bound
    
    Trading Rules:
    1. Price opens inside VA:
       - Expect rotation to POC
       - Look for breakout of VAH/VAL for direction
    
    2. Price opens outside VA:
       - If accepted outside → trending day
       - If rejected → expect rotation back to VA
    
    3. Single prints (low volume nodes):
       - Act as support/resistance
       - Price moves quickly through them
    
    # Python implementation
    import numpy as np
    
    def calculate_volume_profile(df, num_bins=50):
        price_range = np.linspace(df['low'].min(), df['high'].max(), num_bins)
        volume_profile = np.zeros(num_bins - 1)
    
        for i, row in df.iterrows():
            # Distribute volume across price range of candle
            mask = (price_range[:-1] >= row['low']) & (price_range[1:] <= row['high'])
            if mask.any():
                volume_profile[mask] += row['volume'] / mask.sum()
    
        poc_idx = volume_profile.argmax()
        poc_price = (price_range[poc_idx] + price_range[poc_idx + 1]) / 2
    
        # Calculate Value Area (70% of volume)
        sorted_idx = np.argsort(volume_profile)[::-1]
        cumsum = np.cumsum(volume_profile[sorted_idx])
        va_threshold = volume_profile.sum() * 0.70
        va_idx = sorted_idx[cumsum <= va_threshold]
    
        vah = price_range[va_idx.max() + 1]
        val = price_range[va_idx.min()]
    
        return {'poc': poc_price, 'vah': vah, 'val': val}
    

---
  #### **Name**
RSI Divergence with Structure
  #### **Description**
RSI divergence confirmed by price structure break
  #### **When**
Looking for trend exhaustion and reversal setups
  #### **Why It Works**
Divergence shows momentum weakening, structure break confirms reversal
  #### **Example**
    The Problem with Basic Divergence:
    - Divergence can persist for weeks/months in strong trends
    - Many traders lose money buying divergence in downtrends
    
    The Solution: Structure Confirmation
    
    Bullish Divergence Setup:
    1. Price makes lower low
    2. RSI makes higher low (divergence)
    3. WAIT for price to break above prior swing high
    4. Enter on retest of breakout level
    
    def find_rsi_divergence_with_structure(df, rsi_period=14):
        df['rsi'] = ta.RSI(df['close'], timeperiod=rsi_period)
    
        signals = []
    
        for i in range(50, len(df)):
            window = df.iloc[i-50:i+1]
    
            # Find recent swing lows
            price_lows = find_swing_lows(window['low'])
            rsi_lows = find_swing_lows(window['rsi'])
    
            if len(price_lows) >= 2 and len(rsi_lows) >= 2:
                # Bullish divergence: lower price low, higher RSI low
                price_div = window['low'].iloc[price_lows[-1]] < window['low'].iloc[price_lows[-2]]
                rsi_div = window['rsi'].iloc[rsi_lows[-1]] > window['rsi'].iloc[rsi_lows[-2]]
    
                if price_div and rsi_div:
                    # Find swing high between the lows
                    swing_high = window['high'].iloc[price_lows[-2]:price_lows[-1]].max()
    
                    # Check if price broke above swing high
                    if df['close'].iloc[i] > swing_high:
                        signals.append({
                            'index': i,
                            'type': 'bullish_divergence_confirmed',
                            'entry': swing_high,
                            'stop': window['low'].iloc[price_lows[-1]]
                        })
    
        return signals
    
  #### **Success Rate**
~55-60% win rate, but 2:1+ R:R makes it positive expectancy

---
  #### **Name**
Fibonacci Confluence Zones
  #### **Description**
Multiple Fibonacci levels from different swings creating high-probability zones
  #### **When**
Identifying optimal entry points in trending markets
  #### **Why It Works**
Self-fulfilling prophecy - enough traders watch same levels to create reactions
  #### **Example**
    Fibonacci Confluence Method:
    
    1. Identify major swing (weekly/daily)
    2. Draw retracement from that swing
    3. Identify secondary swing (daily/4H)
    4. Draw retracement from secondary swing
    5. Look for overlap zones (confluence)
    
    Key Levels:
    - 0.382 (38.2%): Shallow retracement, strong trends
    - 0.500 (50%): Psychological level
    - 0.618 (61.8%): Deep retracement, still healthy
    - 0.786 (78.6%): Last chance, often failed moves
    
    Confluence Example:
    - Major swing 61.8% = $45,230
    - Minor swing 38.2% = $45,150
    - Prior resistance turned support = $45,300
    - Zone: $45,150 - $45,300 (high probability support)
    
    def find_fib_confluence(df, major_swing, minor_swing, tolerance=0.005):
        """Find where Fibonacci levels from different swings overlap"""
    
        fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
    
        major_fibs = []
        minor_fibs = []
    
        major_range = major_swing['high'] - major_swing['low']
        minor_range = minor_swing['high'] - minor_swing['low']
    
        for level in fib_levels:
            if major_swing['direction'] == 'up':
                major_fibs.append(major_swing['high'] - (major_range * level))
            else:
                major_fibs.append(major_swing['low'] + (major_range * level))
    
            if minor_swing['direction'] == 'up':
                minor_fibs.append(minor_swing['high'] - (minor_range * level))
            else:
                minor_fibs.append(minor_swing['low'] + (minor_range * level))
    
        # Find confluences
        confluences = []
        for mj in major_fibs:
            for mn in minor_fibs:
                if abs(mj - mn) / mj < tolerance:
                    confluences.append({
                        'price': (mj + mn) / 2,
                        'strength': 'strong' if abs(mj - mn) / mj < tolerance/2 else 'moderate'
                    })
    
        return sorted(confluences, key=lambda x: x['price'])
    

---
  #### **Name**
Market Structure Break (MSB)
  #### **Description**
Identifying trend changes through structural breaks
  #### **When**
Determining if a trend has ended and new direction beginning
  #### **Why It Works**
Trends are defined by higher highs/lows or lower highs/lows - breaking this structure signals change
  #### **Example**
    Market Structure Basics:
    
    Uptrend: Higher Highs (HH) + Higher Lows (HL)
    Downtrend: Lower Highs (LH) + Lower Lows (LL)
    
    Break of Structure (BOS):
    - In uptrend: Price breaks below prior HL
    - In downtrend: Price breaks above prior LH
    
    Change of Character (CHoCH):
    - First BOS after extended trend
    - Often marks the beginning of reversal
    
    Order Block:
    - The last bullish candle before bearish move (in reversal)
    - The last bearish candle before bullish move (in reversal)
    - Acts as high-probability retest zone
    
    def detect_structure_break(df, lookback=20):
        """Detect market structure breaks"""
    
        swing_highs = find_swing_points(df['high'], 'high', lookback)
        swing_lows = find_swing_points(df['low'], 'low', lookback)
    
        signals = []
    
        for i in range(lookback * 2, len(df)):
            # Get recent structure
            recent_highs = [h for h in swing_highs if h['index'] < i][-3:]
            recent_lows = [l for l in swing_lows if l['index'] < i][-3:]
    
            if len(recent_highs) >= 2 and len(recent_lows) >= 2:
                # Uptrend structure
                is_uptrend = (
                    recent_highs[-1]['price'] > recent_highs[-2]['price'] and
                    recent_lows[-1]['price'] > recent_lows[-2]['price']
                )
    
                # Check for break
                if is_uptrend:
                    # Break below prior higher low = structure break
                    if df['close'].iloc[i] < recent_lows[-1]['price']:
                        signals.append({
                            'index': i,
                            'type': 'bearish_structure_break',
                            'broken_level': recent_lows[-1]['price'],
                            'order_block': find_last_bullish_candle(df, i)
                        })
    
        return signals
    

---
  #### **Name**
VWAP Mean Reversion
  #### **Description**
Trading deviations from volume-weighted average price
  #### **When**
Intraday trading, identifying overextended moves
  #### **Why It Works**
VWAP represents fair value - institutions benchmark against it
  #### **Example**
    VWAP Bands Strategy:
    
    VWAP = Σ(Price × Volume) / Σ(Volume)
    
    Standard Deviation Bands:
    - +1σ: Price overextended to upside
    - +2σ: Extremely overextended (mean reversion likely)
    - -1σ: Price undervalued
    - -2σ: Extremely undervalued
    
    Trading Rules:
    1. Trend day (price stays above/below VWAP):
       - Trade pullbacks to VWAP as support/resistance
       - Don't fade strong trends
    
    2. Range day (price oscillates around VWAP):
       - Fade moves to ±2σ bands
       - Target VWAP for mean reversion
    
    3. Identify day type by 10:30 AM:
       - Gap + hold above VWAP = trend day up
       - Gap + fail to hold = rotation day
    
    import numpy as np
    
    def calculate_vwap_bands(df, num_std=2):
        """Calculate VWAP with standard deviation bands"""
    
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['tp_volume'] = df['typical_price'] * df['volume']
    
        df['cum_tp_vol'] = df['tp_volume'].cumsum()
        df['cum_vol'] = df['volume'].cumsum()
    
        df['vwap'] = df['cum_tp_vol'] / df['cum_vol']
    
        # Calculate rolling variance for bands
        df['squared_diff'] = ((df['typical_price'] - df['vwap']) ** 2) * df['volume']
        df['cum_squared'] = df['squared_diff'].cumsum()
        df['variance'] = df['cum_squared'] / df['cum_vol']
        df['std'] = np.sqrt(df['variance'])
    
        for i in range(1, num_std + 1):
            df[f'vwap_upper_{i}'] = df['vwap'] + (df['std'] * i)
            df[f'vwap_lower_{i}'] = df['vwap'] - (df['std'] * i)
    
        return df
    

## Anti-Patterns


---
  #### **Name**
Indicator Stacking
  #### **Description**
Using multiple indicators that measure the same thing
  #### **Why**
RSI, Stochastics, CCI all measure momentum - they'll give same signals
  #### **Instead**
    # Bad: Redundant indicators
    - RSI + Stochastics + CCI (all momentum)
    - MACD + Moving Averages (MACD is derived from MAs)
    
    # Good: Complementary indicators
    - Trend: One moving average or price structure
    - Momentum: One oscillator (RSI or MACD)
    - Volume: Volume profile or OBV
    - Volatility: ATR or Bollinger Width
    
    # Rule: One indicator per category, max 3-4 total
    

---
  #### **Name**
Curve Fitting Backtests
  #### **Description**
Optimizing indicators until backtest looks perfect
  #### **Why**
Overfitted parameters won't work in live trading - you fit to noise
  #### **Instead**
    # Bad: Optimized parameters
    "RSI 7 with 23/77 levels on 4H BTC gave 87% win rate!"
    
    # Why it's bad:
    - Specific to that asset, timeframe, period
    - Won't generalize to future data
    - You found noise, not signal
    
    # Good: Robust parameters
    - Use default or well-researched parameters
    - Test across multiple assets and timeframes
    - Use walk-forward optimization
    - Out-of-sample testing mandatory
    
    # If edge disappears with standard parameters, there is no edge
    

---
  #### **Name**
Cherry-Picked Chart Examples
  #### **Description**
Showing only times pattern worked, ignoring failures
  #### **Why**
Every pattern fails sometimes - need to know failure rate
  #### **Instead**
    # Bad: "Look at this perfect head and shoulders!"
    - Shows 3 examples where it worked
    - Ignores 7 times it failed
    
    # Good: Statistical approach
    - "Head and shoulders breaks down 63% of time (Bulkowski)"
    - "Average decline is 16%"
    - "Failed patterns reverse 45%+ when neckline holds"
    
    # Always ask:
    1. What's the sample size?
    2. What's the failure rate?
    3. What defines failure/success?
    

---
  #### **Name**
Ignoring Higher Timeframe
  #### **Description**
Taking signals against the prevailing trend
  #### **Why**
Fighting the trend is fighting probability - trend continuation more likely than reversal
  #### **Instead**
    # Bad: Buying 15m oversold in daily downtrend
    "RSI is at 20, time to buy!"
    
    # Why it fails:
    - Oversold can get more oversold
    - You're buying into selling pressure
    - Higher timeframe dominates
    
    # Good: Timeframe alignment
    1. Weekly: Determine major trend
    2. Daily: Identify setup zone
    3. 4H/1H: Time entry
    
    # Only trade when all timeframes agree or neutral
    

---
  #### **Name**
Moving Average Crossover Systems
  #### **Description**
Blindly trading golden/death crosses
  #### **Why**
Extremely lagging, whipsaws in ranges, huge drawdowns in trends
  #### **Instead**
    # Bad: Buy golden cross, sell death cross
    - 50 MA crosses above 200 MA = buy
    - In range-bound markets: whipsaw city
    - In trends: enters late, exits late
    
    # Why it persists:
    - Looks great on strongly trending backtests
    - Survivorship bias (we remember when it worked)
    
    # Better uses for MAs:
    - Dynamic support/resistance (not signals)
    - Trend filter (only long above 200, short below)
    - Mean reversion anchor (trade pullbacks to MA)
    
    # If you must use crossovers, add filters:
    - ADX > 25 (confirm trend)
    - Volume increase on cross
    - Price structure confirmation
    

---
  #### **Name**
Predicting with Patterns
  #### **Description**
Treating patterns as guaranteed predictions
  #### **Why**
Patterns are probabilities, not certainties - every pattern can fail
  #### **Instead**
    # Bad thinking:
    "This is a cup and handle, it WILL go up"
    
    # Good thinking:
    "This is a cup and handle formation. Historically, these break up 65% of the time
     with average move of 20%. My entry is the breakout, stop is below the handle,
     target is the cup depth projected up. If it fails, I lose 1R."
    
    # Pattern = setup with edge
    # Not pattern = prediction of future
    
    # Always have:
    - Defined entry
    - Defined stop
    - Defined target
    - Acceptance that it might fail
    