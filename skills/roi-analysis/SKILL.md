---
name: roi-analysis
description: Use when calculating marketing ROI on Xiaohongshu, measuring campaign return on investment, analyzing cost per acquisition, evaluating marketing spend efficiency, or proving marketing value to stakeholders
---

# ROI Analysis (ROI分析)

## Overview

ROI (Return on Investment) analysis is the systematic measurement and evaluation of marketing efficiency on Xiaohongshu, calculating returns from investments to optimize spend, justify budgets, and demonstrate business impact through data-driven financial metrics.

## When to Use

**Use when**:
- Calculating campaign or content ROI
- Measuring cost per acquisition (CPA)
- Comparing channel or campaign efficiency
- Justifying marketing budget to stakeholders
- Optimizing resource allocation
- Evaluating long-term customer value vs acquisition cost
- Making data-driven investment decisions
- Proving marketing value to leadership

**Do NOT use when**:
- Tracking basic engagement metrics (use data-analytics)
- Monitoring follower growth (use data-metrics-understanding)
- Analyzing content quality (use content-performance-analysis)

## Core Pattern

**Before** (unclear returns, gut-feel budgeting):
```
❌ "Not sure if this campaign is profitable"
❌ "We think it's working, spends keep increasing"
❌ "Can't justify budget to finance team"
❌ "No idea which channel performs best"
```

**After** (clear ROI, data-driven budgeting):
```
✅ "Campaign A: 5.2x ROAS, generates ¥520K per ¥100K spend"
✅ "Channel B: ¥45 CAC vs Channel C: ¥120 CAC - scale B"
✅ "Marketing drives 35% of revenue, budget justified"
✅ "Shift budget from C to A and B for 40% ROI improvement"
```

**6 Essential ROI Metrics**:
1. **ROAS** (Return on Ad Spend): Revenue / Ad Spend
2. **ROI** (Return on Investment): (Revenue - Cost) / Cost × 100%
3. **CPA** (Cost Per Acquisition): Spend / New Customers
4. **CAC** (Customer Acquisition Cost): Marketing Spend / New Customers
5. **CLV** (Customer Lifetime Value): Avg Purchase × Frequency × Lifespan
6. **Payback Period**: Time to recoup acquisition investment

## Quick Reference

| Metric | Formula | Good Benchmark | Use Case | Calculation Frequency |
|--------|--------|----------------|----------|----------------------|
| **ROAS** | Revenue ÷ Ad Spend | 3-5x good, 10x excellent | Ad efficiency | Per campaign, monthly |
| **ROI** | (Revenue - Cost) ÷ Cost × 100% | 200%+ good | Overall profitability | Per campaign, quarterly |
| **CPA** | Spend ÷ Acquisitions | ¥50-150 varies | Acquisition cost | Per campaign, monthly |
| **CAC** | Marketing Spend ÷ New Customers | Minimize | Investment efficiency | Monthly, quarterly |
| **CLV** | Avg Order × Frequency × Lifespan | 3× CAC minimum | Long-term value | Quarterly, annually |
| **Payback** | Acquisition Cost ÷ (Monthly Profit × Margin) | <12 months | Risk assessment | Per cohort |

## Implementation

### Step 1: Define Investment and Return

**Identify All Investments (Costs)**:
```

Direct Marketing Costs:
✅ Ad spend (Xiaohongshu ads, sponsored content)
✅ Influencer fees (KOL collaborations, endorsements)
✅ Content production costs (photography, video creation, design)
✅ Tool and software subscriptions (analytics, scheduling, editing)
✅ Team salaries and contractor fees (proportional time allocation)
✅ Platform fees and commissions
✅ Event and activity costs (giveaways, contests, launch parties)

Indirect Costs (Optional for Full ROI):
✅ Overhead allocation (office space, equipment, utilities)
✅ Management time (strategy, approval, oversight)
✅ Training and development
✅ Research and planning

Cost Tracking Template:
Campaign Costs:
- Ad spend: ¥X
- Influencer fees: ¥Y
- Production: ¥Z
- Tools: ¥A
- Team time: ¥B
Total Investment: ¥X+Y+Z+A+B

Monthly Recurring Costs:
- Retainer fees: ¥X
- Software subscriptions: ¥Y
- Team salaries: ¥Z
- Content budget: ¥A
Total Monthly: ¥X+Y+Z+A
```

**Define Returns (Revenue)**:
```

Direct Revenue (Trackable):
✅ Product sales from trackable sources
✅ Service bookings
✅ Course or digital product sales
✅ Affiliate commissions earned
✅ Lead generation (assign value per lead)

Attribution Models:
Last-Click Attribution:
- Credit goes to final touchpoint before purchase
- Simple but undervalues awareness activities
- Formula: Revenue from last-click Xiaohongshu content

Multi-Touch Attribution:
- Distribute credit across all touchpoints in customer journey
- More accurate but complex
- Example: Xiaohongshu ad (40%) + Organic search (30%) + Direct (30%)

Lead Value Attribution:
- Lead quality: Marketing Qualified Lead (MQL) = ¥X value
- Conversion rate: 20% of MQLs convert at ¥Y revenue
- Attributed revenue: MQLs × 20% × ¥Y

Example Revenue Tracking:
Month Revenue:
- Direct sales (trackable): ¥150,000
- Lead conversions (20% of 500 leads × ¥300 avg): ¥30,000
- Total Attributed Revenue: ¥180,000
```

### Step 2: Track Marketing Costs

**Cost Collection Process**:
```

Step 1: Establish Cost Categories
Create consistent categories:
- Content Production (creative, design, copy)
- Media Buying (ad spend, boosted posts)
- Influencer Marketing (partnerships, sponsorships)
- Tools & Technology (software, platforms)
- Team & Labor (salaries, contractors, agencies)
- Events & Activities (giveaways, contests, launches)

Step 2: Implement Tracking System
Options:
Option A: Spreadsheet Tracking
- Monthly cost tracker by category
- Invoice tracking and organization
- Manual entry for time allocation
- Template: Date, Category, Description, Amount, Notes

Option B: Accounting Software Integration
- Link to accounting system (QuickBooks, Xero)
- Export marketing expenses
- Automated categorization
- Real-time cost monitoring

Option C: Marketing Project Management
- Track costs by project/campaign
- Assign budget vs actual
- Alert on overspend
- Forecast remaining budget

Step 3: Allocate Time and Resources
For team members:
- Track hours spent on marketing activities
- Calculate hourly cost (salary ÷ monthly hours)
- Allocate time to specific campaigns
- Formula: Hours × Hourly Rate = Labor Cost

Example Calculation:
Marketing Manager: ¥15,000/month ÷ 160 hours = ¥94/hour
Time spent on Campaign A: 40 hours
Labor cost for Campaign A: 40 × ¥94 = ¥3,760

Step 4: Track Indirect Costs (Optional)
For complete ROI picture:
- Overhead allocation (rent, utilities, equipment)
- Use percentage of total costs
- Example: 10% overhead allocation
- Formula: Direct Costs × 1.10 = Total Costs
```

### Step 3: Measure Returns

**Revenue Tracking Methods**:
```

Method 1: Direct Tracking (E-commerce)
Best for: Product sales with clear attribution

Setup:
- Xiaohongshu shop with analytics
- UTM parameters on links
- Unique discount codes per campaign
- Order tagging (source, campaign, content)

Metrics:
- Revenue by campaign
- Revenue by content type
- Revenue by influencer
- Revenue by product
- Conversion rate by source

Example:
Campaign: "Summer Skincare Launch"
UTM: utm_source=xiaohongshu&utm_campaign=summer2025
Code: SUMMER25
Track: All sales with code SUMMER25
Revenue Attributed: ¥75,000

---

Method 2: Lead Generation (B2B or Services)
Best for: Service businesses, consultants, agencies

Setup:
- Lead capture mechanism (forms, DMs)
- Lead quality scoring
- Lead nurturing tracking
- Conversion tracking from lead to customer

Metrics:
- Number of leads generated
- Lead quality score (MQL vs SQL)
- Lead-to-customer conversion rate
- Value per conversion
- Time to conversion

Calculation:
Campaign Cost: ¥20,000
Leads Generated: 200
Cost Per Lead (CPL): ¥20,000 ÷ 200 = ¥100
Conversion Rate: 20% (40 leads become customers)
Value Per Customer: ¥2,000 (avg project)
Revenue: 40 × ¥2,000 = ¥80,000
ROI: (¥80,000 - ¥20,000) ÷ ¥20,000 = 300%

---

Method 3: Brand Awareness (Harder to measure)
Best for: Long-term brand building, not immediate sales

Setup:
- Brand lift studies
- Surveys and market research
- Share of voice tracking
- Brand search volume
- Social sentiment analysis

Metrics:
- Increase in brand searches
- Improvement in brand sentiment
- Share of conversation in category
- Brand recall and recognition

Value Assignment (Challenging):
- Estimate long-term value of awareness
- Compare to previous periods
- Industry benchmarks
- Delphi method (expert estimation)

Example:
Before Campaign: 5% brand search share in category
After Campaign: 12% brand search share
Increase: 7 percentage points
Category search volume: 100K/month
Incremental brand searches: 7,000/month
Value per branded search: ¥5 (based on conversion)
Attributed Value: 7,000 × ¥5 = ¥35,000/month
```

### Step 4: Calculate ROI Metrics

**Core ROI Calculations**:
```

ROAS (Return on Ad Spend):
Formula: Revenue ÷ Ad Spend
Example: ¥180,000 ÷ ¥50,000 = 3.6x

Interpretation:
- For every ¥1 spent, generate ¥3.60 in revenue
- Benchmark: 3-5x is good, below 3x needs optimization
- Above 5x is excellent, scale the campaign

ROI (Return on Investment):
Formula: (Revenue - Cost) ÷ Cost × 100%
Example: (¥180,000 - ¥80,000) ÷ ¥80,000 × 100% = 125%

Interpretation:
- 125% return means profit is 1.25× the investment
- Positive ROI (>0%) = profitable
- Negative ROI (<0%) = losing money
- Benchmark: 100%+ ROI is good (doubled investment)

CPA (Cost Per Acquisition):
Formula: Spend ÷ Number of Acquisitions
Example: ¥50,000 ÷ 500 customers = ¥100 CPA

Interpretation:
- How much it costs to acquire each customer
- Compare to customer lifetime value
- Target: CPA should be ≤ 1/3 of CLV

CAC (Customer Acquisition Cost):
Formula: Total Marketing Spend ÷ New Customers
Example: ¥80,000 ÷ 500 = ¥160 CAC

Interpretation:
- Includes all marketing costs, not just ad spend
- Broader measure than CPA
- Should be minimized while maintaining quality

CLV (Customer Lifetime Value):
Formula: Avg Order Value × Purchase Frequency × Customer Lifespan

Example Calculation:
- Average Order Value: ¥200
- Purchase Frequency: 3 times/year
- Customer Lifespan: 2 years (makes 6 purchases total)
- CLV = ¥200 × 6 = ¥1,200

CLV:CAC Ratio:
- Target: 3:1 minimum (CLV ≥ 3× CAC)
- Our example: ¥1,200 CLV ÷ ¥160 CAC = 7.5:1 ratio
- Interpretation: Excellent! Each customer worth 7.5× acquisition cost

Payback Period:
Formula: CAC ÷ (Monthly Profit per Customer)

Example:
- CAC: ¥160
- Monthly profit per customer: ¥50
- Payback Period: ¥160 ÷ ¥50 = 3.2 months
- Interpretation: Recover investment in 3.2 months

Break-Even Point:
Formula: Fixed Costs ÷ (Price - Variable Cost %)

Example:
- Campaign Fixed Cost: ¥20,000
- Product Price: ¥200
- Variable Cost (COGS): 40% or ¥80
- Contribution Margin: ¥200 - ¥80 = ¥120
- Break-Even Volume: ¥20,000 ÷ ¥120 = 167 units
```

### Step 5: Analyze and Optimize

**Performance Analysis Framework**:
```

Campaign Comparison:

Campaign A:
- Spend: ¥30,000
- Revenue: ¥120,000
- ROAS: 4.0x
- ROI: 300%
- CPA: ¥60
- Verdict: ✅ Scale

Campaign B:
- Spend: ¥20,000
- Revenue: ¥40,000
- ROAS: 2.0x
- ROI: 100%
- CPA: ¥133
- Verdict: ⚠️ Optimize or pause

Campaign C:
- Spend: ¥50,000
- Revenue: ¥250,000
- ROAS: 5.0x
- ROI: 400%
- CPA: ¥40
- Verdict: ✅ Scale aggressively

Decision Framework:
- ROAS < 2x: Pause immediately, optimize or cancel
- ROAS 2-3x: Optimize before scaling
- ROAS 3-5x: Scale gradually
- ROAS > 5x: Scale as fast as possible

Channel Optimization:
If Channel A: ROAS 5.0x, CPA ¥50
And Channel B: ROAS 2.5x, CPA ¥120
Decision: Shift budget from B to A

Reallocation Strategy:
1. Identify best performers (ROAS > 4x)
2. Identify worst performers (ROAS < 2x)
3. Calculate potential reallocation
4. Test reallocation incrementally
5. Measure impact for 2-4 weeks
6. Complete reallocation if positive

Example Reallocation:
Current Budget: ¥100K split evenly
- Channel A (¥50K): ROAS 5.0x → ¥250K revenue
- Channel B (¥50K): ROAS 2.5x → ¥125K revenue
Total: ¥375K revenue, 3.75x ROAS

Proposed Reallocation:
- Channel A (¥80K): ROAS 5.0x → ¥400K revenue
- Channel B (¥20K): ROAS 2.5x → ¥50K revenue
Total: ¥450K revenue, 4.5x ROAS

Impact: +¥75K revenue (+20%) for same spend
```

**Optimization Strategies**:
```

Strategy 1: Improve ROAS for Underperformers
Tactics:
- Improve ad targeting (narrow audience, better relevance)
- Enhance creative (test new messaging, images)
- Optimize landing page (better conversion)
- Adjust bidding strategy (lower bids, better efficiency)
- Test different content formats

Strategy 2: Reduce CAC
Tactics:
- Improve organic content (reduce reliance on paid)
- Build brand loyalty (increase repeat purchases)
- Focus on high-intent audiences (bottom of funnel)
- Use retargeting (higher conversion, lower cost)
- Negotiate better rates with partners

Strategy 3: Increase CLV
Tactics:
- Improve product quality (higher prices, retention)
- Add complementary products (cross-sell, upsell)
- Build subscription models (recurring revenue)
- Create community and loyalty programs
- Provide exceptional customer service

Strategy 4: Shorten Payback Period
Tactics:
- Focus on quick-win campaigns
- Front-load revenue (initial purchase incentives)
- Improve onboarding (faster time to value)
- Nurture leads more effectively (faster conversion)
- Target decision-ready audiences (high intent)

Strategy 5: Maximize Efficiency
Tactics:
- A/B test all variables systematically
- Eliminate waste (cut worst performers)
- Automate optimization (use platform AI)
- Scale winners aggressively (don't hold back)
- Reinvest profits into growth (compound returns)
```

### Step 6: Report and Justify

**ROI Presentation Structure**:
```

Executive Summary (1 Page):
Campaign Performance Overview:
Total Investment: ¥150,000
Total Revenue Attributed: ¥525,000
Overall ROAS: 3.5x
Overall ROI: 250%
Net Profit: ¥375,000

Key Achievements:
✅ Campaign C exceeded targets (5.0x ROAS)
✅ CPA decreased by 25% (¥120 → ¥90)
✅ CLV increased by 20% (¥1,200 → ¥1,440)
✅ Payback period shortened by 40% (5 → 3 months)

Top 3 Campaigns:
1. Campaign C: ¥50K spend → ¥250K revenue (5.0x ROAS)
2. Campaign A: ¥30K spend → ¥120K revenue (4.0x ROAS)
3. Product Launch: ¥40K spend → ¥140K revenue (3.5x ROAS)

Recommendations:
1. Scale Campaign C by 50% (highest ROAS)
2. Pause Campaign D (lowest ROAS, 1.8x)
3. Reallocate ¥20K from D to C
4. Test video creative in Campaign A (testing showed 15% lift)
5. Invest in retargeting (lower CAC observed)

Expected Impact:
- New Revenue: ¥100K+ from optimization
- Improved ROAS: 4.0x overall (from 3.5x)
- Reduced CPA: ¥80 (from ¥90)

Budget Justification:
Current monthly budget: ¥150,000
Generate: ¥525,000 revenue
Profit: ¥375,000 net
ROI: 250%

Proposed increase:
+¥50,000 budget
Expected +¥175,000 revenue (at 3.5x ROAS)
Net profit: +¥125,000

Break-Even Analysis:
Need ¥50K to generate ¥175K (3.5x)
Break-even achieved within 3 weeks

Risk Assessment:
- Risk: Optimization doesn't achieve expected lift
- Mitigation: Test incrementally, monitor closely
- Exit strategy: Revert to previous allocation if underperforming

Timeline to Results:
Week 1-2: Implement optimizations
Week 3-4: Monitor performance
Week 5-6: Scale winners if successful
Month 2: Full implementation

Confidence Level: High
Based on: Historical data, test results, benchmark comparisons
```

**Stakeholder Communication**:
```

To Finance Team:
"Our summer campaign generated ¥525K revenue on ¥150K investment,
 delivering 350% ROI. Key insights: Video content outperformed
 images by 40%, retargeting reduced CPA by 30%, and product-focused
 campaigns beat brand campaigns by 2x. We recommend increasing budget
 by ¥50K to scale our winners, projecting additional ¥175K revenue
 with 250% ROI. Risk is low: all recommendations are data-backed
 with test validation."

To Executive Team:
"Marketing is now directly contributing 35% of company revenue,
 up from 22% last quarter. Our most efficient campaigns deliver 5x
 return, while underperformers drag down the average. Strategic
 reallocation of budget from low-ROAS to high-ROAS campaigns will
 improve overall efficiency from 3.5x to 4.0x ROI, generating an
 additional ¥100K profit monthly without increasing total spend."

To Team:
"Great work everyone! Campaign C's 5x ROAS is exceptional - let's
 scale it. Campaign D's 1.8x is below target - we're pausing it to
 focus resources on winners. Your creative testing in Campaign A
 showed 15% improvement - let's roll that out across all campaigns.
 Performance data shows retargeting is our secret weapon - let's
 double down there next month."
```

## Common Mistakes

| Mistake | Why Happens | Fix |
|---------|-------------|-----|
| Only tracking ad spend, not total costs | Easier measurement | Track ALL costs including labor, production, tools |
| Not attributing revenue properly | Complex attribution | Use consistent attribution model, track tags |
| Short-term ROI focus only | Pressure for quick wins | Balance short-term ROAS with long-term CLV |
| Ignoring customer lifetime value | Easier to measure acquisition | CLV should be 3× CAC minimum |
| Calculating ROI too early | Excitement to show results | Give campaigns 4-6 weeks before evaluating |
| Not factoring in seasonality | Normal fluctuations | Compare to same period last year |
| Forgetting variable costs | Simpler calculation | Include COGS, fulfillment, commissions |
| Not benchmarking | Don't know what's good | Compare to industry standards, past performance |
| Presentation lacks context | Data overload | Always provide comparison, not just absolute numbers |

## Real-World Impact

**Case Study: ROI Optimization Journey**

A D2C brand implemented comprehensive ROI analysis and optimization.

**Before ROI Analysis**:
- Unclear which campaigns performed best
- Budget allocated equally across channels
- ROAS varied widely (1.8x to 5.0x) but unknown
- CPA high and rising
- No clear optimization direction

**After ROI Implementation** (6 months):

Phase 1: Measurement Setup (Month 1)
- Installed tracking (UTM codes, pixel, attribution)
- Built cost tracking spreadsheet
- Established CLV calculation (¥1,200 per customer)
- Created ROI dashboard

Phase 2: Baseline Analysis (Months 2-3)
- Measured all campaigns for 2 months
- Identified ROAS by campaign (ranged 1.8x to 5.0x)
- Calculated CPA by channel (¥90 to ¥150)
- Discovered top performers and bottom dwellers

Phase 3: Optimization (Months 4-6)
- Shifted 50% budget from low-ROAS to high-ROAS campaigns
- Paused worst performer (saved ¥20K/month)
- Scaled best performer (increased spend by 50%)
- A/B tested creatives (15% improvement)
- Implemented retargeting (reduced CPA by 30%)

**Results** (12 months):
Cost Optimization:
- Reduced wasted spend on poor performers: ¥40K/month
- Lowered average CPA from ¥120 to ¥85 (-29%)
- Improved overall ROAS from 3.2x to 4.1x (+28%)

Revenue Growth:
- Increased revenue from ¥525K to ¥690K (+31%)
- Improved profit margin from 35% to 42%
- Generated incremental profit of ¥120K/month

Budget Reallocation:
- Original budget: ¥150K/month
- Reallocated based on ROI data
- Same investment, ¥165K more revenue (+11% free)
- Improved efficiency: 4.1x vs 3.2x ROAS

Long-term Impact:
- Payback period decreased from 5 months to 3.2 months
- CLV increased from ¥1,200 to ¥1,440 (+20% from better targeting)
- Customer retention improved (targeting better-fit customers)
- Marketing team productivity increased 25% (clear direction)

**Data-Backed Insights**:
- ROI analysis typically uncovers 30-40% waste in marketing spend
- Top 20% of campaigns often drive 60-80% of results (Pareto principle)
- Shifting budget from worst to best performers can increase ROI by 30-50%
- ROAS optimization is more effective than cutting budget
- Campaigns with 3x+ ROAS should scale aggressively
- Campaigns with <2x ROAS should be paused or optimized
- Retargeting often delivers 2-3x better ROI than cold acquisition
- Video content increasingly outperforms static images (40%+ lift)
- CLV:CAC ratio of 3:1 is minimum; 5:1+ is excellent
- ROI-positive channels can be scaled indefinitely if maintain efficiency
- Quarterly ROI reviews catch underperformers 2-3x faster than monthly
- Companies with systematic ROI analysis grow 2.5x faster than those without
- ROI presentation with clear recommendations increases budget approval by 80%

## Related Skills

**REQUIRED**: Use data-analytics (measure performance)
**REQUIRED**: Use data-report (present findings)
**REQUIRED**: Use excel-analytics (calculate metrics)

**Recommended for ROI mastery**:
- **attribution-modeling** - Accurate revenue attribution
- **clv-calculation** - Customer lifetime value analysis
- **cost-optimization** - Reduce spend while maintaining results
- **budget-allocation** - Strategic resource distribution
- **forecasting** - Predict future ROI and performance
- **business-case-development** - Build compelling business cases
