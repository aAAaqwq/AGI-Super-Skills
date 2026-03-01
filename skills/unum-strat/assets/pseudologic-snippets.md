# Unum (Strat) - Pseudologic Snippets

## 0. Universal fee guard

```text
FUNCTION fee_guard(expected_gross_edge_pct, entry_cost_pct, exit_cost_pct, slippage_pct, safety_buffer_pct):
    hurdle = entry_cost_pct + exit_cost_pct + slippage_pct + safety_buffer_pct
    IF expected_gross_edge_pct <= hurdle:
        RETURN REJECT
    IF expected_gross_edge_pct <= hurdle * 1.25:
        RETURN WEAK
    RETURN PASS
```

## 1. Trend / breakout

```text
FOR each instrument on candle close:
    regime_ok = price > slow_ma AND adx > threshold
    breakout_ok = close > rolling_high
    volatility_ok = atr_pct within allowed band
    expected_edge = projected_move_pct

    IF regime_ok AND breakout_ok AND volatility_ok:
        fee_check = fee_guard(expected_edge, entry_cost, exit_cost, slippage, buffer)
        IF fee_check == PASS:
            size = size_from_risk(capital, stop_distance, bucket_rule)
            PLACE passive_limit_entry()
            PLACE controlled_stop_limit()
            PLACE passive_limit_take_profit()
```

## 2. Mean reversion

```text
IF instrument is liquid AND spread is tight:
    oversold = rsi < threshold_low
    far_from_mean = zscore < negative_threshold
    regime_not_trending = adx < max_for_mean_reversion

    IF oversold AND far_from_mean AND regime_not_trending:
        require fee_guard(...)
        enter with passive_limit()
        exit at mean_reversion_target()
```

## 3. Rotation

```text
AT rebalance interval:
    rank universe by momentum, trend_quality, liquidity, cost_penalty
    keep top_n
    remove names failing cost or liquidity filters
    rebalance slowly using passive_orders_only()
```

## 4. Strategic / tactical split

```text
EVERY strategic_interval:
    regime = classify_regime(multi_timeframe_data, macro_context, venue_state)
    allowed_playbook = map_regime_to_playbook(regime)
    risk_budget = size_risk_budget(regime, volatility, drawdown_state)
    write_policy(regime, allowed_playbook, risk_budget)

EVERY tactical_interval:
    policy = read_current_policy()
    IF policy.regime is unclear:
        HOLD
    candidates = scan_for_entries(policy.allowed_playbook)
    IF candidates pass fee and liquidity filters:
        send_to_execution(candidates)
```

## 5. Council critique pattern

```text
proposal = strategist_proposes_plan(data, costs, constraints)
critique_a = skeptic_reviews(proposal)
critique_b = execution_reviewer_reviews(proposal)
final_policy = synthesizer_resolves(proposal, critique_a, critique_b)

IF final_policy.confidence is low:
    HOLD
```

## 6. News as veto / filter

```text
news_items = collect_scoped_news(source_registry, freshness_window)
verified = verify_high_impact_items(news_items)

IF verified contains venue_outage OR delisting OR exploit OR major_event:
    veto_related_trades()

IF verified contains macro_event_window:
    reduce_risk_budget_or_delay_entries()
```
