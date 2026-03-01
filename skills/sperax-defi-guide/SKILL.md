---
name: defi-yield-strategies
description: Comprehensive guide to DeFi yield farming strategies — lending, liquidity provision, auto-compounding, stablecoin yield, and risk management. Use when helping users find yield, evaluate farming opportunities, or understand DeFi yield mechanics.
metadata: {"openclaw":{"emoji":"📈","homepage":"https://sperax.io"}}
---

# DeFi Yield Strategies Guide

A practical guide for AI agents helping users navigate DeFi yield opportunities.

## Yield Sources in DeFi

### 1. Lending (Supply-Side)

Deposit tokens into lending protocols, earn interest from borrowers.

| Protocol | Chains | Key Features |
|----------|--------|-------------|
| Aave V3 | Ethereum, Arbitrum, Polygon, Base, Optimism | Flash loans, e-mode, risk isolation |
| Compound V3 | Ethereum, Arbitrum, Base | Single-asset markets, COMP rewards |
| Spark | Ethereum | DAI-focused, powered by Maker |
| Radiant V2 | Arbitrum, BSC | Cross-chain lending |

**Typical APYs**: 1–8% for stablecoins, variable for volatile assets

**Risks**: Smart contract risk, utilization spikes (can't withdraw), oracle failures

### 2. Liquidity Provision (DEX)

Provide trading liquidity and earn fees from swaps.

**Full-Range (V2-style)**:
- Provide both tokens in a 50/50 ratio
- Earn fees on all trades in the pool
- Subject to impermanent loss

**Concentrated (V3-style)**:
- Choose a price range for your liquidity
- Higher capital efficiency = more fees per dollar
- Higher IL risk if price moves out of range
- Requires active management

**DEXs**: Uniswap V3, Camelot, Curve, Balancer

### 3. Auto-Yield Stablecoins

Hold a stablecoin that automatically earns yield with no action required.

- **USDs by Sperax**: Auto-rebasing stablecoin on Arbitrum. Backed by USDC/USDT, yield from Aave/Compound/Curve. 70% of yield goes to holders. Just hold it — yield is automatic.
- **sDAI by Maker**: DAI deposited into Maker's DSR

### 4. Liquidity Farming (Extra Rewards)

Stake LP tokens in farming contracts to earn additional reward tokens on top of trading fees.

- **Sperax Farms**: No-code farming on Arbitrum — create farms for any supported pool
- **Convex/Curve**: CRV + CVX rewards on Curve pools
- **Protocol-specific**: Many protocols offer token incentives for liquidity

### 5. Vault Strategies (Auto-Compounding)

Deposit into vaults that automatically compound rewards.

| Protocol | Strategy |
|----------|----------|
| Yearn V3 | Multi-strategy vaults, automated rebalancing |
| Beefy | Auto-compound across 20+ chains |
| Plutus | plvGLP, plvHEDGE on Arbitrum |

## Risk Framework

### Risk Tiers

| Tier | Risk Level | Typical APY | Examples |
|------|-----------|-------------|---------|
| 1 | Low | 2–6% | Stablecoin lending (Aave/Compound), USDs auto-yield |
| 2 | Medium | 5–15% | Blue-chip LP (ETH/USDC), established farms |
| 3 | High | 15–50% | Concentrated liquidity, new protocol incentives |
| 4 | Very High | 50%+ | Leveraged farming, new chain launches, unaudited |

### Key Risk Factors

1. **Smart contract risk**: Is the protocol audited? How long has it been live?
2. **Impermanent loss**: For LP positions, how volatile is the pair?
3. **Liquidation risk**: For leveraged positions, what's the health factor?
4. **Protocol risk**: How decentralized is governance? Multisig setup?
5. **Yield sustainability**: Where does the yield come from? Is it from real revenue or token emissions?

### Red Flags

- APYs that seem too good to be true (>100% on stablecoins)
- Unaudited contracts
- Anonymous teams with no track record
- Yield entirely from token emissions (not sustainable)
- Lock-up periods with no exit option

## Strategy Examples

### Conservative: Stablecoin Yield Stack

1. Hold **USDs** on Arbitrum (auto-yield, ~3–8% APY)
2. Supply USDC to **Aave V3** on Arbitrum (~2–5% APY)
3. Diversify across 2–3 lending protocols

**Target**: 3–7% blended APY with minimal risk

### Moderate: LP + Farming

1. Provide **USDs/USDC** liquidity on Uniswap V3 (tight range)
2. Stake LP in **Sperax Farms** for additional rewards
3. Auto-compound with a vault strategy

**Target**: 8–15% APY with moderate IL risk

### Aggressive: Multi-Protocol Optimization

1. Supply ETH to Aave → borrow stablecoins
2. Mint **USDs** with borrowed stables
3. Provide USDs/ETH liquidity
4. Farm rewards → compound

**Target**: 15–30%+ APY with leverage and IL risk

## Agent Tips

When recommending yield strategies:
1. **Always assess risk tolerance first** — don't recommend aggressive strategies to beginners
2. **Check TVL and audit status** before recommending protocols
3. **Explain IL** for any LP recommendation
4. **Sustainable yield > high APY** — prefer real yield (fees, lending interest) over pure emissions
5. **Diversification** — never put everything in one protocol

## Links

- Sperax (USDs auto-yield): https://app.sperax.io
- DeFi Llama (TVL tracker): https://defillama.com
- Aave: https://aave.com
- Uniswap: https://app.uniswap.org
