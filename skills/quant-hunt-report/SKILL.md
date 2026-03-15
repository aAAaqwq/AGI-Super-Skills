# ⚡ Hunt Report — Trade Summary Reporter

Aggregates results from the latest crypto hunt and Elon tweet monitoring runs into a structured report. **Does not execute any trades** — read-only reporting.

## Execution Flow

### Step 1: Read Latest Hunt Results
Read cached results from recent hunt runs (crypto hunt, Elon tweet monitor).

### Step 2: Read Portfolio Snapshot
Load latest portfolio snapshot for context.

### Step 3: Generate Report
Compile a summary report covering:
- Current prices (BTC, ETH, SOL)
- Portfolio value and cash
- Latest hunt results (trades executed or skipped)
- Position alerts (any needing stop-loss/take-profit)
- Strategy layer status (S1 sweet zone, S2 trend, S7 Elon tweets)

### Step 4: Push Report
Send formatted report to configured channel.

## Key Constraint
This skill is **report-only**. New trades → crypto-hunt skill. Stop-loss → position-monitor skill.

## Changelog
- v1.0 (2026-03-15): Initial release
