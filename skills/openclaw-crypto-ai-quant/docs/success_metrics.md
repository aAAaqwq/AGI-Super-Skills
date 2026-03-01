# Success Metrics & Guardrails

Operational metrics and risk limits that define "working" for the strategy factory system.

## Risk Limits

| Metric | Threshold | Action |
|--------|-----------|--------|
| Daily loss limit | -10% of equity (realized PnL, resets UTC 00:00) | Stop all new entries until next UTC day |
| Max equity drawdown | -20% from high water mark (includes unrealized) | Flatten all positions, enter safe mode |
| Max leverage exposure | 5x | Reject entries that would exceed cap |

## Minimum Trade Count Thresholds

| Context | Minimum Trades | Notes |
|---------|---------------|-------|
| Config evaluation (backtest) | 30 | Below this, statistical significance is insufficient to judge a config |
| Rolling live performance | 30 | PF, win rate, Sharpe computed over a sliding window of the last 30 trades |

## Promotion Criteria (Paper to Live)

### Gate 1: Paper Minimum Run

- Run for at least **1 full trading day** or **20 trades**, whichever comes first.
- Log fills, slippage, funding, latency, rejection rate.

### Gate 2: Paper Pass Criteria

All must be met:

- Profit factor >= 1.2
- Max drawdown < 10%
- Slippage stress test at 20 bps still net positive
- No kill-switch triggers during paper run

### Gate 3: Live Size Ramp

| Stage | Size | Minimum Duration | Advance Condition |
|-------|------|-----------------|-------------------|
| 1 | 25% of target | 1 day | No kill-switch triggers |
| 2 | 50% of target | 1 day | No kill-switch triggers |
| 3 | 100% of target | — | Steady state |

Step down or pause immediately if any kill-switch fires during ramp.

## Rotation Criteria (When to Retire a Config)

Trigger rotation if **any** condition is met:

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Rolling profit factor | PF < 1.0 over last 30 trades | Pause config, fall back to safety mode |
| Live drawdown warning | DD > 15% from config-start HWM | Pause config, queue replacement from nightly run |
| Nightly validation fail | Config no longer passes OOS validation suite | Schedule rotation at next deployment window |
| Max config age | 14 days since deployment | Re-validate; retire if no longer passing |

When a config is rotated out, record: config hash, start/stop timestamps, reason for rotation, and final performance summary.

## References

- [Strategy Lifecycle](strategy_lifecycle.md) — state machine and transition triggers
- [Operations Runbook](runbook.md) — emergency stop and kill-switch procedures
