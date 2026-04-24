# Technical Analysis - Validations

## Backtest Validation Required

### **Id**
check-backtest-exists
### **Description**
Technical patterns should have statistical validation
### **Pattern**
pattern|setup|signal
### **File Glob**
**/*.{py,js,ts}
### **Match**
present
### **Context Pattern**
backtest|win_rate|expectancy
### **Message**
Technical pattern should have backtest validation before live trading
### **Severity**
warning
### **Autofix**


## Stop Loss Required

### **Id**
check-stop-loss-defined
### **Description**
Every trade setup must have defined stop loss
### **Pattern**
entry|signal|position
### **File Glob**
**/*.{py,js,ts}
### **Match**
present
### **Context Pattern**
stop|stop_loss|risk
### **Message**
Define stop loss for every trade setup
### **Severity**
error
### **Autofix**


## Multiple Timeframe Alignment

### **Id**
check-multiple-timeframes
### **Description**
Signals should check higher timeframe context
### **Pattern**
signal|entry
### **File Glob**
**/*.{py,js,ts}
### **Match**
present
### **Context Pattern**
timeframe|higher_tf|htf
### **Message**
Consider higher timeframe alignment before signal generation
### **Severity**
warning
### **Autofix**


## Volume Confirmation

### **Id**
check-volume-confirmation
### **Description**
Breakouts and reversals should check volume
### **Pattern**
breakout|reversal|break
### **File Glob**
**/*.{py,js,ts}
### **Match**
present
### **Context Pattern**
volume|vol
### **Message**
Consider volume confirmation for breakout/reversal signals
### **Severity**
info
### **Autofix**


## Indicator Lag Awareness

### **Id**
check-indicator-lag
### **Description**
Document indicator lag in signal generation
### **Pattern**
moving_average|MA|EMA|MACD
### **File Glob**
**/*.{py,js,ts}
### **Match**
present
### **Context Pattern**
lag|delay|late
### **Message**
Document expected lag for lagging indicators
### **Severity**
info
### **Autofix**


## Risk/Reward Calculation

### **Id**
check-risk-reward
### **Description**
Calculate R:R for trade setups
### **Pattern**
target|take_profit|tp
### **File Glob**
**/*.{py,js,ts}
### **Match**
present
### **Context Pattern**
risk|reward|ratio|rr
### **Message**
Calculate risk/reward ratio for trade setups
### **Severity**
warning
### **Autofix**


## Sufficient Sample Size

### **Id**
check-sample-size
### **Description**
Pattern validation needs adequate sample size
### **Pattern**
win_rate|success.*rate|probability
### **File Glob**
**/*.{py,js,ts}
### **Match**
present
### **Context Pattern**
sample|count|n\s*=|trades
### **Message**
Ensure sufficient sample size (30+ trades minimum)
### **Severity**
warning
### **Autofix**


## Out-of-Sample Testing

### **Id**
check-out-of-sample
### **Description**
Backtests should include out-of-sample period
### **Pattern**
backtest|backtesting
### **File Glob**
**/*.{py,js,ts}
### **Match**
present
### **Context Pattern**
out.*sample|oos|walk.*forward|train.*test
### **Message**
Include out-of-sample testing to validate edge
### **Severity**
warning
### **Autofix**


## Transaction Costs Included

### **Id**
check-transaction-costs
### **Description**
Include fees and slippage in backtests
### **Pattern**
backtest|pnl|profit
### **File Glob**
**/*.{py,js,ts}
### **Match**
present
### **Context Pattern**
fee|commission|slippage|cost
### **Message**
Include transaction costs in backtest calculations
### **Severity**
warning
### **Autofix**


## Entry Invalidation Defined

### **Id**
check-entry-invalidation
### **Description**
Define when a setup becomes invalid
### **Pattern**
setup|pattern|entry
### **File Glob**
**/*.{py,js,ts}
### **Match**
present
### **Context Pattern**
invalid|cancel|abort|expire
### **Message**
Define invalidation conditions for trade setups
### **Severity**
info
### **Autofix**
