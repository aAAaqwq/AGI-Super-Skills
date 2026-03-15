---
name: quant-hunt-report
description: Aggregates latest crypto hunt and Elon tweet monitoring results into a structured report. Read-only — does not execute any trades. Use for periodic trade summary reporting.
---

# Hunt Report — Trade Summary

Compile results from recent hunt runs into a single report. **No trades executed.**

## Flow

1. Read cached hunt results (crypto hunt, Elon tweet monitor)
2. Read latest portfolio snapshot
3. Generate report: prices, portfolio, hunt results, position alerts, strategy status
4. Push report to channel
5. Append to daily memory
