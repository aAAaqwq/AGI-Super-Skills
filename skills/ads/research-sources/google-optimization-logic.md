# Google Deep Research 2 — Ad Optimization Tool Logic

> Source: Google Deep Research PDF, "Ad Optimization Tool Logic Request", February 2026
> 18 pages — Bidding decision engines, budget allocation frameworks, conversion tracking, attribution

---

## Google Ads Bidding Decision Engine

### Strategy Selection Decision Tree

```
IF conversions_last_30d < 15:
  → Maximize Clicks (cold start)
  → Max CPC = Target_CPA / (Estimated_CVR × 1.5)
  → Learning period: 3-5 days
  → Monitor: Wait for 15+ conversions before transitioning

ELIF conversions_last_30d >= 15 AND conversions_last_30d < 30:
  → Maximize Conversions (building data)
  → Learning period: 7-14 days
  → Transition trigger: CPA standard deviation < 20% over 14 days
  → THEN move to Target CPA

ELIF conversions_last_30d >= 30 AND no dynamic values:
  → Target CPA
  → Strict threshold: 30+ conversions (50+ ideal)
  → Initial target: 1.1x - 1.2x historical CPA
  → Adjustment rule: Max 10% change every 14 days
  → Never lower by more than 15% at once

ELIF conversions_last_30d >= 50 AND has dynamic values:
  → Target ROAS
  → Requires: Dynamic conversion values assigned
  → Initial target: Exact historical ROAS (don't be aggressive)
  → Formula: Bid = P(conversion) × Predicted_Value × (1 / Target_ROAS)
  → Adjustment rule: Same as tCPA (10% every 14 days)

IF campaign_type == "Brand Protection":
  → Target Impression Share
  → Target: 95-100% on brand keywords
  → No conversion data requirement
  → Use for brand defense campaigns only

IF conversions_last_30d < 15 AND Manual preferred:
  → Manual CPC
  → NOTE: Enhanced CPC (eCPC) deprecated March 2025
  → Use only when insufficient conversion data
  → Review monthly for transition to automated
```

### Portfolio Bid Strategies

**When to use:**
- Multiple low-volume campaigns (<15 conv each but combined >30)
- Cross-campaign budget optimization needed
- **CPC Cap Hack**: Portfolio strategy is the ONLY way to set a maximum CPC bid on Target CPA or Target ROAS campaigns

**Best practices:**
- Group campaigns with similar target CPAs/ROAS
- Minimum 3 campaigns per portfolio for meaningful data sharing
- Don't mix brand and non-brand in same portfolio

---

## Meta Ads Bidding Decision Engine

### Meta Ad Auction Formula

```
Total Value = Bid × Estimated Action Rate + User Value
```

Where:
- **Bid** = Your bid amount (or automated bid)
- **Estimated Action Rate** = Meta's prediction of user taking desired action
- **User Value** = Relevance, quality, post-engagement signals

### Strategy Selection

```
DEFAULT (90% of campaigns):
  → Lowest Cost (no cap)
  → Best for: Most campaigns, starting out, maximizing volume
  → Risk: CPA can spike during high-competition periods

IF need cost predictability:
  → Cost Cap
  → Set at: 1.2x - 1.5x your target CPA
  → Best for: Scaling with margin protection
  → Risk: May under-deliver if cap too aggressive

IF need strict cost control:
  → Bid Cap
  → Set at: 2x - 3x your target CPA
  → Best for: Experienced advertisers with clear unit economics
  → Risk: Significant under-delivery if set too low

IF e-commerce with revenue tracking:
  → ROAS Goal
  → Best for: Advantage+ Shopping Campaigns
  → Requires: Purchase event + dynamic values

IF high-value diverse products:
  → Highest Value
  → Best for: Accounts with wide AOV range
  → Prioritizes high-value conversions
```

### CBO vs ABO Decision

```
IF daily_budget < $100:
  → ABO (Ad Set Budget Optimization)
  → Reason: Need control over spend distribution during testing

IF daily_budget $100-$500:
  → Either (test both)
  → CBO if testing ad sets with similar target audiences
  → ABO if testing vastly different audiences

IF daily_budget > $500:
  → CBO (Campaign Budget Optimization)
  → Reason: Algorithm has enough data to optimize distribution
  → Let Meta allocate to best-performing ad sets
```

### Learning Phase Management

**Exit criteria:** 50 conversions per week per ad set

**Reset triggers (AVOID these during learning):**
- Budget change > 20%
- Any targeting change
- Creative edit (even text changes)
- Bid strategy change
- Pausing for >7 days

**If stuck in "Learning Limited":**
1. Broaden audience (wider targeting)
2. Increase budget
3. Switch to higher-funnel event (e.g., AddToCart instead of Purchase)
4. Consolidate ad sets

---

## Budget Allocation Framework

### Platform Selection Matrix by Business Type

| Business Type | Platform 1 | Platform 2 | Platform 3 | Other | Min Monthly Budget | Primary KPI | Time to Profit |
|--------------|------------|------------|------------|-------|-------------------|-------------|---------------|
| SaaS B2B | LinkedIn 40% | Google 30% | Meta 20% | Other 10% | $5,000 | Pipeline ROI | 3-6 months |
| E-commerce DTC | Meta 50% | Google PMax 30% | TikTok 15% | Email 5% | $3,000 | ROAS / MER | 0-2 months |
| Local Service | Google LSA/Search 60% | Meta 30% | Bing 10% | — | $1,500 | Cost Per Lead | 1 month |
| B2B Enterprise | LinkedIn 60% | Google 20% | ABM Display 20% | — | $10,000 | Pipeline / SQLs | 6-12 months |
| Info Products | YouTube 40% | Meta 40% | Email 20% | — | $2,000 | ROAS / CPL | 1-3 months |
| Mobile App | Apple Search 30% | Google App 30% | Meta/TikTok 40% | — | $5,000 | CPI / LTV | 3-6 months |
| Real Estate | Meta Lead Forms 50% | Google Search 40% | LinkedIn 10% | — | $2,500 | Cost Per Lead | 2-4 months |
| Healthcare | Google Search 70% | Meta Remarketing 30% | — | — | $4,000 | Cost Per Patient | 2-5 months |
| Finance/Fintech | Google Search 50% | Affiliate/Native 30% | LinkedIn 20% | — | $8,000 | CAC / LTV | 4-8 months |
| Agency (Own) | LinkedIn 50% | Meta 30% | Google 20% | — | $1,500 | Cost Per Lead | 1-3 months |

### Budget Scaling Decision Tree

```
20% RULE (Scale Up):
  IF actual_CPA < target_CPA by > 10%
  AND conversions_last_7d >= learning_threshold
  THEN increase budget by 20%
  → Wait 3-5 days before next increase

3x KILL RULE (Pause):
  IF spend > 3x target_CPA
  AND conversions == 0
  THEN pause ad/ad set/campaign immediately
  → Review creative, targeting, landing page

DECREASING RETURNS DETECTION:
  IF CPA increased > 15% after last budget increase
  THEN roll back to previous budget
  → Wait 7 days, try scaling horizontally instead

SATURATION SIGNALS:
  Google: Impression Share > 80% = diminishing returns
  Meta: Frequency > 4.0 (7-day) = audience exhaustion
  TikTok: Frequency > 3.0 = creative fatigue
  → Diversify to new platform or audience
```

### Marketing Efficiency Ratio (MER)

```
MER = Total Revenue / Total Ad Spend

Benchmarks:
  E-commerce: 3.0 - 5.0 (healthy), >5.0 (excellent), <2.0 (danger)
  SaaS: Use LTV:CAC ratio instead (target 3:1)
  Lead Gen: Use Revenue per Lead × Conversion Rate / CPL
```

### Seasonality Adjustments

- **Q4 (Oct-Dec)**: CPMs increase 30-50%
  - Reduce ROAS targets by 20% during holiday season
  - Front-load creative testing in September
  - Increase budgets by 40-60% for Black Friday/Cyber Monday

- **Q1 (Jan-Mar)**: CPMs decrease 20-30% post-holiday
  - Best time for new campaign testing
  - Aggressive customer acquisition (lower competition)

### Incrementality Testing (Geo-Lift)

- Duration: 2-4 weeks minimum
- Holdout: 10% of geographic regions
- Method: Compare conversion rates between exposed and holdout regions
- Statistical significance: p < 0.05

---

## Conversion Tracking Setup by Platform

### Google Ads
```
Required Stack:
1. Global Site Tag (gtag.js) → all pages
2. Enhanced Conversions → enable via gtag or GTM
3. Consent Mode v2 → required for EU/EEA advertisers
4. Server-Side GTM → recommended for data durability
5. Offline Conversion Import → for lead gen (CRM → Google Ads)

Enhanced Conversions Setup:
- Sends hashed first-party data (email, phone, address)
- Improves conversion measurement by ~5-15%
- Required for smart bidding accuracy in cookie-degraded environments

Consent Mode v2:
- consent('default', { ad_storage: 'denied', analytics_storage: 'denied' })
- consent('update', { ad_storage: 'granted' }) // after user consent
- Enables conversion modeling for unconsented users
```

### Meta Ads
```
Required Stack:
1. Meta Pixel → base code on all pages + standard events
2. Conversions API (CAPI) → server-side event forwarding
3. Event Deduplication → event_id matching between Pixel and CAPI
4. EMQ Optimization → pass email, phone, fbp, fbc, external_id

Event Match Quality (EMQ) Targets:
  < 4.0 → Critical (severe data loss)
  4.0-5.9 → Warning (significant signal gaps)
  6.0-7.9 → Acceptable (some optimization possible)
  8.0-10.0 → Excellent (maximum signal strength)

Deduplication Logic:
- Same event_id + same event_name = deduplicated
- Missing event_id = potential double-counting
- Check Events Manager > Overview > Deduplication Rate
```

### TikTok Ads
```
Required Stack:
1. TikTok Pixel → base code + standard events
2. Events API → server-side forwarding
3. ttclid Passback → store ttclid from URL, send with events
4. Advanced Matching → pass hashed email/phone

Key Difference: ttclid (TikTok Click ID) must be captured from
landing page URL params and passed back with conversion events
```

### LinkedIn Ads
```
Required Stack:
1. LinkedIn Insight Tag → all pages
2. Conversions API (CAPI) → server-side events (launched 2025)
3. Offline Conversion Import → CRM data (opportunity created, deal closed)

Best Practice:
- Track both online (form submit) and offline (SQL, opportunity, closed-won)
- Import offline conversions within 90 days of click
- Use for lead quality optimization (bid for SQLs not just leads)
```

### Microsoft Ads
```
Required Stack:
1. UET (Universal Event Tracking) tag → all pages
2. Enhanced Conversions → enable for improved matching
3. Offline Conversion Import → CRM integration
4. Auto-tagging (MSCLKID) → ensure not stripped by CMS

Note: If importing from Google, verify conversion tracking
transferred correctly — goals often break during import
```

---

## Attribution Models

### Platform Defaults (2026)

| Platform | Default Model | Click Window | View Window |
|----------|--------------|-------------|-------------|
| Google Ads | Data-Driven Attribution (DDA) | 30 days | 1 day (YouTube: 3 days) |
| Meta Ads | Statistical model | 7 days | 1 day |
| TikTok Ads | Last touch | 7 days | 1 day |
| LinkedIn Ads | Last touch | 30 days | 7 days |
| Microsoft Ads | Last touch (DDA available) | 30 days | 1 day |

### Cross-Platform Attribution Hierarchy

```
Source of Truth (best to worst):
1. CRM Data (actual revenue, closed deals)
2. MER (Marketing Efficiency Ratio — total rev / total spend)
3. Post-Purchase Surveys ("How did you hear about us?")
4. Google Analytics 4 (cross-channel, multi-touch)
5. Platform-Reported Data (always overclaims)

Rule: Never trust platform-reported ROAS alone.
Always cross-reference with at least 2 other data sources.
```

---

## Worked Examples

### Example 1: $5K E-commerce Account
- Budget split: Meta $2,500 (50%) + Google PMax $1,500 (30%) + TikTok $750 (15%) + Email $250 (5%)
- Target MER: 4.0x ($20K revenue)
- Start with Lowest Cost on Meta, Maximize Conversions on Google
- After 30 days: Transition to Cost Cap (Meta), Target ROAS (Google) if >30 conversions
- TikTok: Lowest Cost, minimum 6 creatives, Spark Ads focus

### Example 2: $20K B2B SaaS Account
- Budget split: LinkedIn $8K (40%) + Google $6K (30%) + Meta $4K (20%) + Other $2K (10%)
- Target: $200 CPL, 10% Lead-to-Opp rate, $2K CAC
- LinkedIn: TLAs 30%, Lead Gen Forms 40%, Retargeting 30%
- Google: Brand Search + Non-Brand tCPA + PMax
- Meta: Founder-led video content → retargeting
- Track: Offline conversions from CRM (SQL, Opp, Closed-Won)

### Example 3: $100K Omni-Channel Account
- Google $40K (40%) + Meta $30K (30%) + TikTok $15K (15%) + LinkedIn $10K (10%) + Microsoft $5K (5%)
- Run quarterly MMM (Google Meridian or Meta Robyn)
- Incrementality testing: Monthly geo-lift on rotating platforms
- MER as north star, platform ROAS as directional signal only
- Dedicated creative team: 20+ new assets per month
