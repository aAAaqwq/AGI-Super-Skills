# Quant Trader starter kit

This kit selects CQO for quantitative research, CDO for data work, and CFO for risk and financial review. It is for research and paper-trading evaluation, not live execution or financial advice.

## Safe install

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace quant-trader
./install.sh --source "$PWD" --destination /path/to/review-workspace --apply quant-trader
```

Run the first command as a preview. Apply only after reviewing the proposed `workspace-cqo`, `workspace-cdo`, and `workspace-cfo` paths. Existing files and skill directories are preserved.

## Evaluation prompts

- CDO: “Profile this licensed historical dataset for gaps, survivorship bias, leakage, and timestamp errors.”
- CQO: “Design a reproducible backtest with costs, slippage, walk-forward evaluation, and failure criteria.”
- CFO: “Review drawdown, concentration, liquidity, and operational risk. Do not recommend or place a trade.”

No bundled strategy is represented as profitable, live-validated, or production-ready. Use isolated test data, independent review, and human-controlled paper-trading before considering any further use.

See [the setup guide](../../setup.md) for verification and recovery.
