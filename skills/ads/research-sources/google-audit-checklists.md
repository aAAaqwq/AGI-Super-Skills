# Google Deep Research 1 — Ad Audit Checklists & Scoring System

> Source: Google Deep Research PDF, "Ad Audit Checklist & Scoring System", February 2026
> 29 pages — Complete audit checklists for 5 platforms with weighted scoring methodology

---

## Executive Summary: Deterministic Auditing

The 2026 paradigm shift demands **Deterministic Auditing** based on two pillars:
1. **Signal Integrity** — Is the platform receiving clean, complete conversion data?
2. **Algorithmic Freedom** — Is the platform AI given enough room to optimize?

---

## Standardized Scoring Methodology

### Weighted Scoring Algorithm

```
S_total = Σ(C_pass × W_sev × W_cat) / Σ(C_total × W_sev × W_cat) × 100
```

Where:
- `C_pass` = checks that passed (1 or 0)
- `W_sev` = severity weight of the check
- `W_cat` = category weight for that platform

### Severity Multipliers

| Severity | Multiplier | Description |
|----------|-----------|-------------|
| Critical | 5.0 | Immediate revenue/data loss risk |
| High | 3.0 | Significant performance drag |
| Medium | 1.5 | Optimization opportunity |
| Low | 0.5 | Best practice, minor impact |

### Category Weights by Platform

**Google Ads:**
| Category | Weight |
|----------|--------|
| Conversion Tracking | 25% |
| Wasted Spend / Negatives | 20% |
| Account Structure | 15% |
| Keywords & Quality Score | 15% |
| Ads & Assets | 15% |
| Settings & Targeting | 10% |

**Meta Ads:**
| Category | Weight |
|----------|--------|
| Pixel / CAPI Health | 30% |
| Creative (Diversity & Fatigue) | 30% |
| Account Structure | 20% |
| Audience & Targeting | 20% |

**LinkedIn Ads:**
| Category | Weight |
|----------|--------|
| Technical Setup | 25% |
| Audience Quality | 25% |
| Creative & Formats | 20% |
| Lead Gen Forms | 15% |
| Bidding & Budget | 15% |

**TikTok Ads:**
| Category | Weight |
|----------|--------|
| Technical Setup | 25% |
| Creative Quality | 30% |
| Bidding & Learning | 20% |
| Structure & Settings | 15% |
| Performance | 10% |

**Microsoft Ads:**
| Category | Weight |
|----------|--------|
| Technical Setup | 25% |
| Syndication & Bidding | 20% |
| Structure & Audience | 20% |
| Creative & Extensions | 20% |
| Settings & Performance | 15% |

### Grading Thresholds

| Grade | Score Range | Label |
|-------|-----------|-------|
| A | 90-100 | Excellent |
| B | 75-89 | Good |
| C | 60-74 | Needs Improvement |
| D | 40-59 | Poor |
| F | <40 | Critical |

### Quick Wins Logic

```
IF Severity == "High" OR Severity == "Critical"
AND Remediation_Time < 15 minutes
THEN flag as "Quick Win"
```

---

## Google Ads Audit Checklist (G01-G61)

### Structure (G01-G12)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| G01 | Campaign naming convention | Medium | Structure | Consistent naming pattern (e.g., [Brand]_[Type]_[Geo]_[Target]) |
| G02 | Ad group naming convention | Medium | Structure | Matches campaign naming pattern |
| G03 | Single theme ad groups | High | Structure | Each ad group targets 1 keyword theme (≤15 keywords) |
| G04 | Campaign count per objective | High | Structure | ≤5 campaigns per funnel stage/objective |
| G05 | Brand vs Non-Brand separation | Critical | Structure | Brand and non-brand traffic in separate campaigns |
| G06 | PMax campaign present for eligible accounts | Medium | Structure | PMax active for accounts with conversion history |
| G07 | Search + PMax overlap check | High | Structure | Brand exclusions configured in PMax when Search brand campaign exists |
| G08 | Budget allocation matches priority | High | Structure | Top-performing campaigns not budget-limited |
| G09 | Campaign daily budget vs spend | Medium | Structure | No campaigns hitting daily budget cap before 6PM |
| G10 | Ad schedule configured | Low | Structure | Ad schedule set if business has operating hours |
| G11 | Geographic targeting accuracy | High | Structure | Location targeting = "People in" not "People in or interested in" (for local) |
| G12 | Network settings | High | Structure | Search Partners and Display Network disabled for Search campaigns (unless intentional) |

### Search Terms & Negatives (G13-G19)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| G13 | Search term audit recency | Critical | Wasted Spend | Search terms reviewed within last 14 days |
| G14 | Negative keyword lists exist | Critical | Wasted Spend | ≥3 theme-based negative lists (Competitor, Jobs, Free, Irrelevant) |
| G15 | Account-level negatives applied | High | Wasted Spend | Negative lists applied at account or all-campaign level |
| G16 | Wasted spend on irrelevant terms | Critical | Wasted Spend | <5% of spend on irrelevant search terms (last 30 days) |
| G17 | Broad match + smart bidding pairing | Critical | Wasted Spend | No Broad Match keywords running on Manual CPC |
| G18 | Close variant pollution | High | Wasted Spend | Exact/Phrase match not triggering for irrelevant close variants |
| G19 | Search term visibility | Medium | Wasted Spend | >60% of search term spend is visible (not hidden) |

### Quality Score (G20-G25)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| G20 | Average Quality Score | High | Keywords & QS | Account-wide average QS ≥ 6/10 |
| G21 | Critical QS keywords | Critical | Keywords & QS | <10% of keywords with QS ≤ 3 |
| G22 | Expected CTR component | High | Keywords & QS | <20% of keywords with "Below Average" expected CTR |
| G23 | Ad relevance component | High | Keywords & QS | <20% of keywords with "Below Average" ad relevance |
| G24 | Landing page experience | High | Keywords & QS | <15% of keywords with "Below Average" landing page experience |
| G25 | QS improvement opportunity | Medium | Keywords & QS | Top 20 spend keywords all have QS ≥ 7 |

### Ads, RSA & PMax (G26-G35)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| G26 | RSA per ad group | High | Ads & Assets | ≥1 RSA per ad group (≥2 recommended) |
| G27 | RSA headline count | High | Ads & Assets | ≥8 unique headlines per RSA (ideal: 12-15) |
| G28 | RSA description count | Medium | Ads & Assets | ≥3 descriptions per RSA (ideal: 4) |
| G29 | RSA Ad Strength | High | Ads & Assets | <10% RSAs with "Poor" Ad Strength |
| G30 | RSA pinning strategy | Medium | Ads & Assets | Pinning used strategically (not all positions pinned) |
| G31 | PMax asset group completeness | Critical | Ads & Assets | Each asset group: ≥5 images, ≥2 logos, ≥1 video |
| G32 | PMax video assets present | High | Ads & Assets | Native video uploaded (not auto-generated) in all formats (16:9, 1:1, 9:16) |
| G33 | PMax asset group count | Medium | Ads & Assets | ≥2 asset groups per PMax campaign (intent-segmented) |
| G34 | PMax final URL expansion | High | Ads & Assets | Final URL expansion configured intentionally (ON for discovery, OFF for control) |
| G35 | Ad copy relevance to keywords | High | Ads & Assets | Headlines contain primary keyword variants |

### Bidding & Budget (G36-G41)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| G36 | Smart bidding strategy active | High | Bidding | All campaigns with ≥15 conv/30d use automated bidding |
| G37 | Target CPA/ROAS reasonableness | Critical | Bidding | Targets within 20% of historical performance |
| G38 | Learning phase status | High | Bidding | <25% of campaigns currently in "Learning" or "Learning Limited" |
| G39 | Budget constrained campaigns | High | Bidding | Top-performing campaigns show "Eligible" not "Limited by Budget" |
| G40 | Manual CPC justification | Medium | Bidding | Manual CPC only on campaigns with <15 conv/month |
| G41 | Portfolio bid strategies | Medium | Bidding | Low-volume campaigns grouped into portfolio strategies |

### Conversions (G42-G49)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| G42 | Conversion actions defined | Critical | Conversion Tracking | ≥1 primary conversion action configured |
| G43 | Enhanced conversions enabled | Critical | Conversion Tracking | Enhanced conversions active for primary conversions |
| G44 | Server-side tracking | High | Conversion Tracking | Server-side GTM or Google Ads API conversion import active |
| G45 | Consent Mode v2 | Critical | Conversion Tracking | Consent Mode v2 implemented (required for EU/EEA) |
| G46 | Conversion window appropriate | Medium | Conversion Tracking | Click-through window matches sales cycle (7d ecom, 30-90d B2B) |
| G47 | Micro vs macro conversion separation | High | Conversion Tracking | Only macro conversions set as "Primary" for bidding |
| G48 | Attribution model | Medium | Conversion Tracking | Data-driven attribution (DDA) selected (default since 2023) |
| G49 | Conversion value assignment | High | Conversion Tracking | Dynamic conversion values for e-commerce; value rules for lead gen |

### Extensions, Audiences & Landing Pages (G50-G61)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| G50 | Sitelink extensions | High | Settings & Targeting | ≥4 sitelinks per campaign |
| G51 | Callout extensions | Medium | Settings & Targeting | ≥4 callouts per campaign |
| G52 | Structured snippets | Medium | Settings & Targeting | ≥1 structured snippet set |
| G53 | Image extensions | Medium | Settings & Targeting | Image extensions active for search campaigns |
| G54 | Call extensions (if applicable) | Medium | Settings & Targeting | Call extensions with call tracking for phone-based businesses |
| G55 | Lead form extensions | Low | Settings & Targeting | Lead form extensions tested for lead gen accounts |
| G56 | Audience segments applied | High | Settings & Targeting | Remarketing and in-market audiences in Observation mode |
| G57 | Customer Match lists | High | Settings & Targeting | Customer Match list uploaded and refreshed <30 days |
| G58 | Placement exclusions | High | Settings & Targeting | Account-level placement exclusions (games, apps, MFA sites) |
| G59 | Landing page mobile speed | High | Settings & Targeting | Mobile LCP < 2.5s (ideal < 2.0s) |
| G60 | Landing page relevance | High | Settings & Targeting | Landing page H1/title matches ad group theme |
| G61 | Landing page schema markup | Medium | Settings & Targeting | Product/FAQ/Service schema present |

---

## Meta Ads Audit Checklist (M01-M40)

### Technical / Signal Integrity (M01-M10)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| M01 | Meta Pixel installed | Critical | Pixel/CAPI | Pixel firing on all pages |
| M02 | Conversions API (CAPI) active | Critical | Pixel/CAPI | Server-side events sending alongside pixel |
| M03 | Event deduplication | Critical | Pixel/CAPI | event_id matching between pixel and CAPI events |
| M04 | Event Match Quality (EMQ) | Critical | Pixel/CAPI | EMQ score ≥ 6.0 for Purchase event (ideal ≥ 8.0) |
| M05 | Domain verification | High | Pixel/CAPI | Business domain verified in Business Manager |
| M06 | Aggregated Event Measurement (AEM) | High | Pixel/CAPI | Top 8 events configured and prioritized correctly |
| M07 | Standard events vs custom events | High | Pixel/CAPI | Using standard events (Purchase, AddToCart, Lead) not custom |
| M08 | Conversion API Gateway | Medium | Pixel/CAPI | CAPI Gateway considered for simplified server-side setup |
| M09 | iOS attribution window | High | Pixel/CAPI | 7-day click / 1-day view attribution configured |
| M10 | Data freshness | Medium | Pixel/CAPI | Events firing in real-time (no >1hr lag in Events Manager) |

### Structure & Learning Phase (M11-M18)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| M11 | Campaign count | High | Account Structure | ≤5 active campaigns per country/funnel stage |
| M12 | CBO vs ABO appropriateness | High | Account Structure | CBO for >$500/day campaigns, ABO for testing <$100/day |
| M13 | Learning phase status | Critical | Account Structure | <30% of ad sets in "Learning Limited" |
| M14 | Learning phase resets | High | Account Structure | No unnecessary edits causing learning phase resets |
| M15 | Advantage+ Shopping campaign | Medium | Account Structure | ASC active for e-commerce accounts with catalog |
| M16 | Ad set consolidation | High | Account Structure | No overlapping ad sets targeting same audience |
| M17 | Budget distribution | High | Account Structure | No single ad set getting <$10/day (insufficient for optimization) |
| M18 | Campaign objective alignment | High | Account Structure | Campaign objective matches actual business goal |

### Audience & Targeting (M19-M24)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| M19 | Audience overlap | High | Audience & Targeting | <30% overlap between active ad sets (Audience Overlap tool) |
| M20 | Custom Audience freshness | High | Audience & Targeting | Website Custom Audiences refreshed within 180 days |
| M21 | Lookalike source quality | Medium | Audience & Targeting | Lookalike source audiences ≥1,000 users from high-value events |
| M22 | Advantage+ Audience testing | Medium | Audience & Targeting | Advantage+ Audience tested vs manual targeting |
| M23 | Exclusion audiences | High | Audience & Targeting | Purchasers/converters excluded from prospecting campaigns |
| M24 | First-party data utilization | High | Audience & Targeting | Customer list uploaded for Custom Audience + Lookalike creation |

### Creative (M25-M32)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| M25 | Creative format diversity | Critical | Creative | ≥3 formats active (static image, video, carousel) |
| M26 | Creative volume per ad set | High | Creative | ≥3 creatives per ad set (ideal: 5-8 for Andromeda) |
| M27 | Video aspect ratios | High | Creative | 9:16 vertical video present for Reels/Stories placements |
| M28 | Creative fatigue detection | Critical | Creative | No creatives with CTR drop >30% over 14 days while still active |
| M29 | Hook rate (video) | High | Creative | Video ads: <50% skip rate in first 3 seconds |
| M30 | Social proof utilization | Medium | Creative | Top organic posts boosted as partnership/Spark ads |
| M31 | UGC / social-native content | High | Creative | ≥30% of creative assets are UGC or social-native style |
| M32 | Advantage+ Creative | Medium | Creative | Advantage+ Creative enhancements enabled (test vs control) |

### Placements (M33-M34)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| M33 | Advantage+ Placements | Medium | Account Structure | Advantage+ Placements enabled (unless specific exclusion needed) |
| M34 | Placement performance review | Medium | Account Structure | Placement breakdown reviewed monthly; underperformers excluded |

### Settings & Reporting (M35-M40)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| M35 | Attribution setting | High | Account Structure | 7-day click / 1-day view attribution (not 1-day click only) |
| M36 | Cost control / bid strategy | High | Account Structure | Appropriate bid strategy per objective (Cost Cap for margin, Lowest Cost for volume) |
| M37 | Frequency cap monitoring | High | Audience & Targeting | Ad set frequency <4.0 in last 7 days (prospecting) |
| M38 | Breakdown reporting | Medium | Account Structure | Age, gender, placement, platform breakdowns reviewed monthly |
| M39 | UTM parameters | Medium | Account Structure | UTM parameters on all ad URLs for GA4 attribution |
| M40 | A/B testing active | Medium | Creative | At least 1 active A/B test (Experiments) running |

---

## LinkedIn Ads Audit Checklist (L01-L25)

### Technical (L01-L02)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| L01 | Insight Tag installed | Critical | Technical | LinkedIn Insight Tag firing on all pages |
| L02 | Conversions API (CAPI) | High | Technical | Server-side conversion tracking active |

### Audience (L03-L09)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| L03 | Job title targeting precision | High | Audience | Job title targeting uses specific titles, not just functions |
| L04 | Company size filtering | Medium | Audience | Company size matches ICP (Ideal Customer Profile) |
| L05 | Seniority level targeting | High | Audience | Seniority level appropriate for offer (C-suite for enterprise, Manager for mid-market) |
| L06 | Matched Audiences | High | Audience | Website retargeting and contact list audiences created |
| L07 | ABM company lists | Medium | Audience | Target company lists uploaded for ABM campaigns |
| L08 | Audience expansion setting | Medium | Audience | Audience expansion OFF for precise targeting, ON for scale |
| L09 | Predictive audiences | Medium | Audience | Predictive audiences tested for lookalike targeting |

### Creative (L10-L13)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| L10 | Thought Leader Ads | High | Creative | TLAs active and receiving ≥30% of budget for B2B |
| L11 | Ad format diversity | High | Creative | ≥2 ad formats tested (single image, video, document, carousel) |
| L12 | Video ads present | Medium | Creative | Video ads tested (despite lower efficiency score) |
| L13 | Creative refresh cadence | Medium | Creative | Creative refreshed every 4-6 weeks |

### Lead Gen Forms (L14-L15)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| L14 | Lead Gen Form optimization | High | Lead Gen | Form has ≤5 fields (reduce friction) |
| L15 | Lead Gen Form CRM integration | High | Lead Gen | Form synced to CRM in real-time (not manual download) |

### Bidding (L16-L17)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| L16 | Bid strategy appropriate | High | Bidding | CPS (Cost Per Send) for Message Ads; Maximum Delivery or Manual for Sponsored Content |
| L17 | Budget sufficiency | High | Bidding | Daily budget ≥$50 for Sponsored Content (LinkedIn minimum for learning) |

### Structure (L18-L20)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| L18 | Campaign objective alignment | High | Structure | Campaign objective matches funnel stage |
| L19 | A/B testing | Medium | Structure | Active A/B test on creative or audience |
| L20 | Frequency monitoring | High | Structure | Message frequency cap not exceeded (1 per 30-45 days) |

### Performance (L21-L25)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| L21 | CTR benchmark | High | Performance | Sponsored Content CTR ≥ 0.44% |
| L22 | CPC benchmark | Medium | Performance | CPC within industry benchmark range |
| L23 | Lead quality tracking | High | Performance | Lead-to-opportunity rate tracked (not just CPL) |
| L24 | Conversion tracking attribution | Medium | Performance | 30-day click / 7-day view window configured |
| L25 | Demographics report review | Medium | Performance | Job title and company breakdown reviewed monthly |

---

## TikTok Ads Audit Checklist (T01-T25)

### Technical (T01-T02)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| T01 | TikTok Pixel installed | Critical | Technical | Pixel firing on all relevant pages |
| T02 | Events API active | High | Technical | Server-side events sending via Events API with ttclid passback |

### Structure (T03-T04)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| T03 | Campaign structure | High | Structure | Separate campaigns for prospecting vs retargeting |
| T04 | Smart+ utilization | Medium | Structure | Smart+ campaigns tested for eligible objectives |

### Creative (T05-T10)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| T05 | Creative volume | Critical | Creative | ≥6 creative assets per ad group |
| T06 | Vertical video format | Critical | Creative | All video assets 9:16 (1080x1920) |
| T07 | Native-looking content | High | Creative | Ads look organic (not polished/corporate) |
| T08 | Hook strategy | High | Creative | First 1-2 seconds have attention-grabbing hook |
| T09 | Creative lifespan | High | Creative | No creative active >7 days with declining CTR |
| T10 | Spark Ads utilization | High | Creative | Spark Ads (creator content) tested and active |

### Bidding & Learning (T11-T13)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| T11 | Bid strategy | High | Bidding | Appropriate bid strategy (Lowest Cost for volume, Cost Cap for efficiency) |
| T12 | Budget sufficiency | High | Bidding | Daily budget ≥20x target CPA per ad group |
| T13 | Learning phase | High | Bidding | Ad groups achieving ≥50 conversions/week to exit learning |

### Settings (T14-T16)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| T14 | Search Ads Toggle | High | Settings | Search Ads Toggle enabled for all campaigns |
| T15 | Placement selection | Medium | Settings | Appropriate placements selected (TikTok, Pangle, etc.) |
| T16 | Dayparting | Low | Settings | Ad schedule aligned with target audience activity |

### Performance (T17-T19)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| T17 | CTR benchmark | High | Performance | CTR ≥ 1.0% for in-feed ads |
| T18 | CPA target | High | Performance | CPA within target range (no ad group >3x target CPA) |
| T19 | Video completion rate | Medium | Performance | Average video watch time ≥6 seconds |

### Extended Structure & Creative (T20-T25)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| T20 | TikTok Shop integration | Medium | Structure | Shop catalog connected for e-commerce accounts |
| T21 | Video Shopping Ads (VSA) | Medium | Creative | VSA tested for product catalog accounts |
| T22 | Caption SEO | High | Creative | Captions include high-intent keywords for search discovery |
| T23 | Sound/music usage | Medium | Creative | Trending or engaging audio used (not silent ads) |
| T24 | CTA button | Medium | Creative | Appropriate CTA button selected (not default) |
| T25 | Safe zone compliance | High | Creative | Key content within safe zone (X:40-940, Y:150-1470) |

---

## Microsoft Ads Audit Checklist (MS01-MS20)

### Technical (MS01-MS03)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| MS01 | UET tag installed | Critical | Technical | Universal Event Tracking tag firing on all pages |
| MS02 | Enhanced conversions | High | Technical | Enhanced conversions enabled |
| MS03 | Google Ads import validation | High | Technical | If imported: verify all settings transferred correctly (especially URLs) |

### Syndication (MS04-MS05)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| MS04 | Search partner network | High | Syndication | Syndicated search partners reviewed and low-performers excluded |
| MS05 | Audience Network settings | Medium | Syndication | Audience Network enabled only if testing intentionally |

### Bidding (MS06-MS07)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| MS06 | Bid strategy alignment | High | Bidding | Bid strategy matches campaign goal and conversion volume |
| MS07 | Target New Customers (PMax) | Medium | Bidding | "Target New Customers" enabled for growth campaigns |

### Structure (MS08-MS09)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| MS08 | Campaign structure | High | Structure | Mirrors Google Ads structure (if imported) or follows best practices |
| MS09 | Budget allocation | Medium | Structure | Budget proportional to Bing search volume (typically 20-30% of Google) |

### Audience (MS10)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| MS10 | LinkedIn profile targeting | High | Audience | LinkedIn targeting utilized (unique to Microsoft) for B2B |

### Creative (MS11-MS13)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| MS11 | RSA asset count | High | Creative | RSA headlines and descriptions match Google Ads best practices |
| MS12 | Multimedia Ads | Medium | Creative | Multimedia Ads tested (unique to Microsoft — rich visual format) |
| MS13 | Ad copy uniqueness | Medium | Creative | Ad copy not just cloned from Google — optimized for Bing demographics |

### Settings (MS14-MS15)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| MS14 | Copilot placement | Medium | Settings | Copilot chat placement enabled for PMax campaigns |
| MS15 | Conversion goals | High | Settings | Conversion goals configured (not using Google-imported goals without verification) |

### Performance (MS16-MS18)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| MS16 | CPC vs Google comparison | Medium | Performance | Microsoft CPC 20-40% lower than Google for same keywords |
| MS17 | Conversion rate comparison | Medium | Performance | Microsoft CVR comparable to Google (flag if >50% lower) |
| MS18 | Impression share | Medium | Performance | Impression share tracked for brand and top non-brand terms |

### Extensions (MS19-MS20)

| ID | Check | Severity | Category | Pass Criteria |
|----|-------|----------|----------|---------------|
| MS19 | Action Extension | Medium | Creative | Action Extension utilized (unique to Microsoft) |
| MS20 | Filter Link Extension | Medium | Creative | Filter Link Extension tested for product/service categories |
