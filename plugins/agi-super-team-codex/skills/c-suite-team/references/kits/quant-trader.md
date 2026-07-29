# Quant Research runbook

This runbook supports research and paper-trading evaluation only. It is not financial advice, does not place trades, and remains **Validation pending** for behavioral outcomes until a matching harness receipt exists.

## Input

Provide a falsifiable hypothesis, licensed historical data or an approved data route, market universe, time period, cost assumptions, constraints, and failure criteria. The core is `ceo`, `cqo`, `cdo`, `cfo`, and `governor`; use `cro` for source and literature review.

## Waves

1. `ceo` bounds the decision and forbids live execution.
2. `cro` maps prior evidence while `cdo` audits lineage, timestamps, leakage, missingness, and survivorship bias.
3. `cqo` specifies the backtest, walk-forward evaluation, baselines, costs, and falsification tests.
4. `cfo` reviews drawdown, liquidity, concentration, and capital assumptions.
5. `governor` independently checks reproducibility and rejects profitability or production-readiness claims not supported by the artifacts.

## Artifacts

- Research hypothesis and evidence map.
- Versioned dataset contract and reproducible backtest specification.
- Risk memorandum with costs, drawdown, and failure conditions.
- Independent gate decision with limitations.

## Checks

- `data-lineage-recorded`: origin, license, timestamps, and transformations are named.
- `leakage-controls-defined`: look-ahead and survivorship risks have explicit tests.
- `costs-and-slippage-modeled`: evaluation includes realistic execution assumptions.
- `no-live-trade-action`: no order, account, or production market action is performed.

## Capability fallback

Native workers may independently audit data, research design, and financial risk when file ownership is separate. Otherwise, produce manual task packets. Same-context review must be labeled as non-independent, and missing market or compute capabilities must be reported rather than invented.

## Human approval

Any account connection, credential use, data purchase, paper-trading activation, or step toward live execution requires separate human authorization outside this runbook.
