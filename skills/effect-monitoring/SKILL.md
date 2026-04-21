---
name: effect-monitoring
description: Use when monitoring Xiaohongshu marketing campaign performance, tracking promotion effectiveness, analyzing advertising ROI, measuring influencer collaboration results, evaluating activity success rates, or optimizing marketing spend allocation
---

# Effect Monitoring (效果监测)

## Overview

Effect monitoring is the systematic tracking and analysis of marketing campaign performance on Xiaohongshu, measuring ROI, engagement, conversion, and overall impact to optimize future marketing investments and strategy decisions.

## When to Use

**Use when**:
- Running marketing campaigns (ads, KOL collaborations, activities)
- Tracking promotion performance and effectiveness
- Analyzing marketing ROI and cost per acquisition
- Evaluating influencer collaboration results
- Optimizing marketing spend and budget allocation
- Comparing performance across different campaigns
- Generating marketing performance reports

**Do NOT use when**:
- Monitoring daily content performance (use data-analytics)
- Tracking account growth metrics (use data-analytics)
- Analyzing organic engagement (use data-analytics)
- Monitoring non-marketing activities

## Core Pattern

**Before** (blind marketing, no measurement):
```
❌ "Launched campaign, spent ¥10,000, not sure how it performed"
❌ "Influencer posted, got some likes, unclear if it drove sales"
❌ "Multiple campaigns running, can't tell which is working"
❌ "No tracking, just hoping for the best"
```

**After** (data-driven monitoring and optimization):
```
✅ "Campaign A: ¥10,000 spend, ¥50,000 revenue, 5x ROAS, 12% conversion"
✅ "Influencer B: ¥5,000 fee, 100,000 views, 2.3% CTR, 350 conversions"
✅ "Campaign B outperformed A by 40% - reallocate budget next month"
✅ "Real-time dashboard shows campaign C underperforming, paused immediately"
```

**3-Level Monitoring Framework**:
1. **Exposure Level** - Views, impressions, reach, CPM
2. **Engagement Level** - Likes, comments, shares, saves, engagement rate
3. **Conversion Level** - Clicks, leads, sales, ROAS, CPA, customer acquisition cost

## Quick Reference

| Metric Type | Key Metrics | Benchmarks | Tools |
|-------------|-------------|------------|-------|
| **Exposure** | Views, impressions, reach | 10,000+ views for paid | Platform analytics |
| **Engagement** | Likes, comments, shares, saves | 5-10% engagement rate | Platform analytics |
| **Click-Through** | CTR, link clicks | 2-5% CTR for ads | Platform analytics |
| **Conversion** | Sales, leads, sign-ups | 1-3% conversion rate | E-commerce analytics |
| **ROI** | ROAS, ROCE, cost per acquisition | 3-5x ROAS good | Custom calculations |
| **Cost** | CPM, CPC, cost per lead | ¥50-150 CPM | Platform analytics |

## Implementation

### Step 1: Define Monitoring Objectives

**Clarify Campaign Goals**:
```
Primary Objective (choose one):
- Brand Awareness: Maximize reach and impressions
- Engagement: Maximize likes, comments, shares
- Traffic: Drive clicks to website or store
- Conversion: Generate sales, leads, or sign-ups
- Customer Acquisition: Acquire new customers at target cost

Secondary Objectives:
- Grow follower count by X amount
- Generate user-generated content
- Build email list or private domain
- Increase brand mentions and sentiment
- Launch new product successfully

Target Metrics:
- ROAS (Return on Ad Spend): 3-5x target
- CPA (Cost Per Acquisition): ¥50-200 target
- CTR (Click-Through Rate): 2-5% target
- Conversion Rate: 1-3% target
- Engagement Rate: 5-10% target
```

**Set Up Tracking Framework**:
```
Campaign Types to Monitor:
1. Paid Advertising (信息流广告, 搜索广告)
2. KOL/Influencer Collaborations
3. Activity Campaigns (促销活动, 打卡活动)
4. Content Marketing (品牌内容, 种草内容)
5. Live Commerce (直播带货)

Tracking Timeline:
- Pre-Launch: Baseline metrics (3-7 days before)
- Launch: Real-time monitoring (first 24 hours critical)
- Mid-Campaign: Daily check-ins, optimize as needed
- Post-Campaign: Final analysis and report (7 days after)
```

### Step 2: Set Up Tracking Infrastructure

**Platform Analytics Setup**:
```
Xiaohongshu Professional Account (专业号):
✅ Enable professional account analytics
✅ Set up UTM parameters for external links
✅ Create campaign tags for different initiatives
✅ Enable e-commerce tracking (if applicable)
✅ Set up conversion tracking pixels

Key Platform Metrics to Track:
- Content performance by post
- Audience demographics and behavior
- Traffic sources and referrals
- Follower growth and churn
- Engagement trends over time
```

**External Analytics Setup**:
```
Google Analytics / Website Analytics:
✅ Set up goal tracking (purchases, sign-ups)
✅ Enable e-commerce tracking
✅ Create UTM tagged URLs for campaigns
✅ Set up custom dimensions for campaign attribution
✅ Configure cross-domain tracking

CRM / Customer Data:
✅ Tag customers by source (Xiaohongshu, campaign, influencer)
✅ Track customer lifetime value by acquisition channel
✅ Monitor repeat purchase rate by source
✅ Calculate customer acquisition cost accurately

Third-Party Tools:
✅ Huitun Data (灰豚数据) - Competitor and campaign tracking
✅ Chanmama (蝉妈妈) - Live commerce analytics
✅ Xinhong Data (新红数据) - Influencer performance tracking
```

**Campaign Tracking Template**:
```
Campaign Name: [Brand] [Type] [Date] [Objective]
Example: "BrandA_KOLCollab_June2024_Awareness"

UTM Parameters:
utm_source=xiaohongshu
utm_medium=cpc | influencer | activity | content
utm_campaign=[campaign_name]
utm_content=[influencer_name | post_id]

Unique Tracking Links:
- Create unique link for each influencer
- Create unique link for each creative variation
- Create unique link for each placement/channel
```

### Step 3: Monitor Exposure Metrics

**Real-Time Exposure Tracking**:
```
Key Exposure Metrics:
1. Impressions (曝光量)
   - Total times content displayed
   - Benchmark: 50,000+ for paid campaigns

2. Reach (触达人数)
   - Unique users who saw content
   - Benchmark: 30,000+ unique users

3. View-Through Rate (VTR)
   - Percentage of impressions viewed
   - Benchmark: 60-80% for video content

4. Frequency (频次)
   - Average times each user saw content
   - Optimal: 2-4 exposures per user

Monitoring Frequency:
- First 24 hours: Check every 2-4 hours
- Days 2-7: Check twice daily
- Week 2-4: Check daily
- After week 4: Weekly check-ins sufficient
```

**Cost Metrics**:
```
Cost Efficiency Metrics:
1. CPM (Cost Per Mille / Cost Per 1,000 Impressions)
   - Formula: (Total Spend / Impressions) × 1,000
   - Benchmark: ¥50-150 CPM for Xiaohongshu

2. CPC (Cost Per Click)
   - Formula: Total Spend / Clicks
   - Benchmark: ¥1-5 CPC for good targeting

3. Cost Per View (CPV)
   - Formula: Total Spend / Video Views
   - Benchmark: ¥0.01-0.05 per view

4. Cost Per Engagement (CPE)
   - Formula: Total Spend / Total Engagements
   - Benchmark: ¥0.5-2 per engagement

Alert Thresholds:
- CPM > ¥200: Check targeting, creative may be fatigued
- CPC > ¥10: Audience too narrow or creative not compelling
- CPV > ¥0.10: Content not resonating, revise creative
```

### Step 4: Monitor Engagement Metrics

**Engagement Quality Tracking**:
```
Core Engagement Metrics:
1. Likes (点赞数)
   - Basic engagement signal
   - Benchmark: 3-5% of views

2. Comments (评论数)
   - Deep engagement signal
   - Benchmark: 0.5-1% of views
   - Quality: Positive sentiment > 80%

3. Shares/Forwards (分享数)
   - Viral potential signal
   - Benchmark: 0.2-0.5% of views
   - High share = strong resonance

4. Saves (收藏数)
   - Purchase intent signal
   - Benchmark: 1-2% of views
   - High saves = high conversion potential

5. Engagement Rate
   - Formula: (Likes + Comments + Shares + Saves) / Views
   - Benchmark: 5-10% good, 10%+ excellent
```

**Sentiment Analysis**:
```
Comment Sentiment Tracking:
Positive Indicators:
- "种草了" (got hooked/seeded)
- "想要" (want it)
- "链接在哪" (where's the link)
- "已经买了" (already bought)
- Emoji usage (❤️, 🔥, 👍)

Negative Indicators:
- "太贵了" (too expensive)
- "不好用" (doesn't work well)
- "广告" (ad/commercial)
- "踩雷" (disappointment)

Sentiment Score Formula:
Sentiment % = (Positive Comments / Total Comments) × 100

Benchmark:
- Excellent: >80% positive
- Good: 60-80% positive
- Needs improvement: <60% positive
```

**Influencer Engagement Benchmarking**:
```
Compare Influencer Performance:
Influencer Engagement Quality Score =
(Average Engagement Rate / Influencer's Follower Count) × 1,000

Benchmark:
- Mega-influencers (1M+ followers): 1-3
- Macro-influencers (100K-1M): 3-10
- Micro-influencers (10K-100K): 10-50
- Nano-influencers (1K-10K): 50-200

Red Flags:
- Engagement rate < 1% of follower count (possible fake followers)
- Comments are generic (好美, 喜欢, 支持) without substance
- Like:comment ratio > 20:1 (normal is 10:1)
- Sudden spike in followers then drop (bought followers)
```

### Step 5: Monitor Conversion Metrics

**Click-Through Tracking**:
```
Link Click Metrics:
1. CTR (Click-Through Rate)
   - Formula: (Clicks / Impressions) × 100
   - Benchmark: 2-5% for paid campaigns

2. Click-to-Conversion Rate
   - Formula: (Conversions / Clicks) × 100
   - Benchmark: 1-3% for e-commerce

3. Bounce Rate
   - Percentage who click but leave immediately
   - Benchmark: <40% good, <60% acceptable

4. Time on Site
   - Average time spent after clicking
   - Benchmark: 2+ minutes good signal
```

**Sales and Revenue Tracking**:
```
E-commerce Conversion Metrics:
1. Total Sales Revenue (GMV)
   - Gross merchandise value from campaign
   - Compare to campaign cost for ROAS

2. ROAS (Return on Ad Spend)
   - Formula: Revenue / Ad Spend
   - Benchmark:
     * 1-2x: Breakeven or slight profit
     * 3-5x: Good performance
     * 5-10x: Excellent performance
     * 10x+: Exceptional, scale campaign

3. CPA (Cost Per Acquisition)
   - Formula: Ad Spend / Number of Customers Acquired
   - Benchmark:
     * Low-ticket (<¥100): ¥20-50 CPA
     * Mid-ticket (¥100-500): ¥50-150 CPA
     * High-ticket (>¥500): ¥150-500 CPA

4. AOV (Average Order Value)
   - Formula: Total Revenue / Number of Orders
   - Compare to regular AOV
   - Campaign AOV > Regular AOV = good sign

5. Customer Lifetime Value (CLV)
   - Formula: Average Purchase Value × Purchase Frequency × Customer Lifespan
   - Compare CLV to CPA
   - Target: CLV > 3× CPA for sustainable growth
```

**Lead Generation Tracking**:
```
Lead Metrics (for non-ecommerce):
1. Total Leads Generated
   - Form submissions, sign-ups, inquiries
   - Benchmark: 2-5% conversion from clicks

2. Cost Per Lead (CPL)
   - Formula: Ad Spend / Number of Leads
   - Benchmark: ¥50-200 CPL depending on industry

3. Lead Quality Score
   - Track lead qualification rate
   - Benchmark: 30-50% become qualified leads

4. Conversion to Customer
   - Percentage of leads who become customers
   - Benchmark: 10-30% depending on sales cycle
```

### Step 6: Calculate and Analyze ROI

**Comprehensive ROI Calculation**:
```
Total Campaign ROI Analysis:

Campaign Costs:
- Ad spend: ¥X
- Influencer fees: ¥Y
- Content production: ¥Z
- Platform fees: ¥A
- Team time: ¥B
Total Cost = X + Y + Z + A + B

Campaign Returns:
- Direct revenue: ¥R
- Attributed revenue (assisted conversions): ¥S
- Customer lifetime value: ¥C
- Earned media value (organic from paid): ¥E
Total Return = R + S + C + E

ROI Formulas:
1. Simple ROAS = R / Total Cost
2. Attributed ROAS = (R + S) / Total Cost
3. Full ROI = (R + S + C + E - Total Cost) / Total Cost

Decision Matrix:
ROAS < 2x: Unprofitable, optimize or pause
ROAS 2-3x: Marginal, improve creatives/targeting
ROAS 3-5x: Good, scale gradually
ROAS 5-10x: Excellent, scale aggressively
ROAS 10x+: Exceptional, maximize scale
```

**Attribution Modeling**:
```
Campaign Attribution Approaches:
1. Last-Click Attribution
   - Credit goes to final touchpoint before purchase
   - Simple but undervalues awareness campaigns

2. First-Click Attribution
   - Credit goes to initial touchpoint
   - Values discovery but ignores nurturing

3. Multi-Touch Attribution (Recommended)
   - Distributes credit across all touchpoints
   - Xiaohongshu often plays mid-funnel role
   - More accurate for multi-channel campaigns

4. Time Decay Attribution
   - Touchpoints closer to purchase get more credit
   - Reflects recency effect on decision-making

Recommended: Use multi-touch attribution for complete picture
```

### Step 7: Generate Performance Reports

**Daily Monitoring Dashboard**:
```
Daily Report Template:
Campaign Name: [Name]
Date: [Date]
Days Active: [X]

Today's Performance:
- Spend: ¥X (¥Y total to date)
- Impressions: X (Y total)
- Clicks: X (Y total)
- Conversions: X (Y total)
- Revenue: ¥X (¥Y total)
- ROAS: X.x (Y.y total to date)

Key Changes vs Yesterday:
- Performance: ↑↓ X%
- Insights: [What happened, why]

Alerts: [Any issues or opportunities]

Actions Taken: [Optimizations performed]
```

**Weekly Performance Summary**:
```
Weekly Report Template:
Campaign: [Name]
Week: [Date Range]

Executive Summary:
[2-3 sentences on overall performance]

Performance Table:
| Metric | This Week | Last Week | Change |
|--------|-----------|-----------|--------|
| Spend  | ¥X        | ¥Y        | ±Z%    |
| Revenue| ¥X        | ¥Y        | ±Z%    |
| ROAS   | X.x       | Y.y       | ±Z%    |
| CTR    | X.x%      | Y.y%      | ±Z%    |
| Conv.  | X.x%      | Y.y%      | ±Z%    |

Top Performing:
- Creatives: [Which creatives worked best]
- Audiences: [Which audiences converted best]
- Placements: [Which placements performed best]

Low Performing:
- Underperforming elements to fix

Optimization Actions:
[Changes made this week]

Next Week's Plan:
[Planned adjustments]
```

**Campaign Final Report**:
```
Post-Campaign Analysis Template:
Campaign: [Name]
Duration: [Start Date] - [End Date]

Campaign Objectives:
[What we set out to achieve]

Objectives Achieved:
- Objective 1: [Status and details]
- Objective 2: [Status and details]

Overall Performance:
- Total Spend: ¥X
- Total Revenue: ¥Y
- ROAS: X.x
- vs Target: (above/below target by X%)

Key Metrics Breakdown:
[Full metrics table with benchmarks]

Learnings and Insights:
1. What worked:
   - [Specific success factors]

2. What didn't work:
   - [Specific failures]

3. Surprises:
   - [Unexpected outcomes]

4. Audience Insights:
   - [Demographics, behaviors discovered]

5. Creative Insights:
   - [Messages, formats that resonated]

Recommendations for Next Campaign:
1. [Specific recommendation 1]
2. [Specific recommendation 2]
3. [Specific recommendation 3]

Budget Allocation Recommendation:
[How to optimize future spend]
```

## Common Mistakes

| Mistake | Why Happens | Fix |
|---------|-------------|-----|
| Only tracking vanity metrics (likes, views) | Easy to measure, feel good | Focus on business metrics (sales, leads, ROAS) |
| Not setting up proper tracking beforehand | Excitement to launch | Set up ALL tracking before spending any money |
| Ignoring attribution, claiming all sales | Want to show good results | Use proper attribution modeling for accuracy |
| Checking too frequently, overreacting | Anxiety, desire to optimize | Set check intervals, look at trends not daily blips |
| Comparing campaigns with different objectives | Apples-to-oranges comparison | Only compare campaigns with similar goals |
| Not tracking long-term value (CLV) | Focus on immediate results | Track customer lifetime value, not just first purchase |
| Ignoring qualitative feedback | Hard to quantify | Monitor comments, sentiment, customer feedback |
| Pausing campaigns too early | Impatience, early underperformance | Give campaigns 7-14 days to optimize |
| Not A/B testing creatives or audiences | Seems good enough | Always test variations, optimize winners |
| Failing to document learnings | Moving to next campaign | Document insights for future campaigns |

## Real-World Impact

**Case Study: Campaign Optimization Through Monitoring**

A skincare brand spent ¥50,000 on Xiaohongshu influencer campaigns with unclear results.

**Before monitoring**:
- Spent ¥50,000 across 10 influencers
- Unknown ROI, felt "okay but not great"
- No data to guide future decisions

**After implementing monitoring**:
- Discovered 2 influencers drove 80% of results
- ROAS varied from 0.8x to 8.5x across influencers
- Creatives with before/after images outperformed lifestyle shots by 3x
- Audience 25-34 converted 2x better than 18-24

**Optimization actions**:
- Reallocated budget to top 2 performers (3x spend increase)
- Paused underperforming influencers
- Updated creative brief to emphasize before/after content
- Shifted targeting to 25-34 demographic

**Results**:
- Next campaign: ¥50,000 spend → ¥350,000 revenue (7x ROAS)
- Increased from estimated 2x ROAS to measured 7x ROAS
- Data-driven decisions improved efficiency by 250%

**Data-Backed Insights**:
- Campaigns with proper monitoring outperform blind campaigns by 2-3x
- Real-time optimization can improve ROAS by 30-50%
- Top 20% of influencers often drive 60-80% of results (pareto principle)
- Creative optimization typically improves CTR by 20-40%
- Multi-touch attribution reveals 30-50% more value than last-click
- Monitoring increases marketing budget efficiency by 40-60%

## Related Skills

**REQUIRED**: Use data-analytics (analyze performance data)
**REQUIRED**: Use KOL-collaboration (track influencer performance)
**REQUIRED**: Use advertising (monitor ad performance)

**Recommended for comprehensive monitoring**:
- **roi-analysis** - Deep dive into return on investment calculations
- **attribution-modeling** - Advanced multi-touch attribution techniques
- **a-b-testing** - Test creatives, audiences, placements scientifically
- **dashboard-creation** - Build real-time monitoring dashboards
- **customer-lifetime-value** - Calculate long-term customer value

**Use effect-monitoring AFTER**:
- KOL-collaboration (track influencer campaign results)
- advertising (monitor ad performance)
- activity-planning (measure activity success)
