# Unum (Strat) - Compact Decision Tree

## Start with defaults
If unspecified:
- exposure style -> spot / cash / fully-paid
- entry -> limit only
- exit -> limit only
- protective order -> stop-limit or controlled equivalent
- leverage -> off
- shorting -> off

## Step 1 - collect the essentials
Need:
- venue
- asset class
- exact fees
- capital
- universe
- timeframe
- minimum notional / liquidity constraints

## Step 2 - reject obvious bad ideas
Reject or down-rank when:
- gross edge does not clear realistic round-trip cost
- minimum order size forces oversized risk
- account is too small for target turnover
- passive-fill assumptions are unrealistic
- backtest ignores fees, spread, slippage, or leakage
- user wants complex architecture without evidence it helps

## Step 3 - choose the simplest viable family
Default order:
1. trend / breakout
2. selective mean reversion
3. rotation
4. verified range / grid
5. pair / spread
6. market making
7. derivatives expansion
8. LLM-only prediction -> reject

## Step 4 - choose architecture depth
- deterministic only -> default
- strategic / tactical split -> if multi-timeframe or portfolio coordination is needed
- council-enhanced -> only for critique diversity or complex systems

## Step 5 - choose deployment questions
Ask hardware / OS only if:
- local models are wanted
- councils are in scope
- deployment planning is requested
- OpenClaw routing or nodes matter

## Step 6 - choose news usage
- no news layer -> acceptable for many simple systems
- news as veto/filter -> preferred default
- news as direct trigger -> only with strong evidence and strict verification
