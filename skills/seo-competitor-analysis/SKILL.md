---
name: seo-competitor-analysis
description: "Deep SEO competitor analysis — keyword mapping, backlink profiling, content strategy audit, SERP share analysis, and technical SEO comparison. Use when user asks to 'analyze competitor SEO', 'competitor keyword analysis', 'backlink comparison', 'SEO competitive intelligence', 'competitor content strategy', or 'SEO gap analysis'."
license: MIT
metadata:
  version: 1.0.0
  domains: [seo, competitor-analysis, competitive-intelligence]
  type: specialist
---

# SEO Competitor Analysis Pro

Deep-dive SEO competitive intelligence — uncover competitors' keyword strategies, backlink profiles, content gaps, and technical advantages.

## When to Use
- Analyzing competitor SEO strategies
- Finding keyword gaps and opportunities
- Comparing backlink profiles
- Auditing competitor content strategies
- Benchmarking technical SEO
- Planning SEO attack strategies

## Capabilities

### 1. Competitor Discovery
```bash
# Find organic competitors for a keyword
WebSearch: "{keyword} site:ahrefs.com competitors"
WebSearch: "{keyword} site:semrush.com organic competitors"

# Find who ranks for your target keywords
WebSearch: "{keyword1}" → note top 5 domains
WebSearch: "{keyword2}" → note top 5 domains
# Domains appearing multiple times = true competitors
```

### 2. Keyword Gap Analysis

**Framework: Find keywords competitors rank for that you don't.**

```markdown
## Keyword Gap: {Your Site} vs {Competitor}

| Keyword | Your Rank | Competitor Rank | Volume | Difficulty | Opportunity |
|---------|-----------|-----------------|--------|------------|-------------|
| {kw1} | Not ranked | #3 | 5,400 | Medium | 🟢 High |
| {kw2} | #15 | #2 | 2,900 | Low | 🟢 High |
| {kw3} | #8 | #5 | 12,000 | High | 🟡 Medium |
```

**Free methods:**
```bash
# Check what pages a competitor has indexed
WebSearch: "site:{competitor.com}"

# Check specific keyword presence
WebSearch: "site:{competitor.com} {keyword}"

# Find their top pages
WebSearch: "site:{competitor.com}" # sort by relevance = their strongest pages
```

### 3. Backlink Profile Analysis

**Free backlink check methods:**
```bash
# Ahrefs free backlink checker
open "https://ahrefs.com/backlink-checker?input={competitor.com}"

# Check referring domains
WebSearch: "link:{competitor.com} -site:{competitor.com}"

# Find competitor's guest posts
WebSearch: "\"{competitor brand}\" guest post OR \"written by\" OR \"contributor\""
```

**Backlink comparison template:**
```markdown
| Metric | Your Site | Competitor A | Competitor B |
|--------|-----------|-------------|-------------|
| Referring Domains | X | X | X |
| Total Backlinks | X | X | X |
| Domain Rating | X | X | X |
| .edu/.gov links | X | X | X |
| Avg Link Quality | X | X | X |
```

### 4. Content Strategy Audit

**Analyze competitor content:**

```bash
# Sitemap analysis
curl -s "https://{competitor.com}/sitemap.xml" | grep -c "<url>" # total pages
curl -s "https://{competitor.com}/sitemap.xml" | grep "<loc>" | head -20

# Blog/content frequency
WebSearch: "site:{competitor.com}/blog" # count results
WebSearch: "site:{competitor.com} after:2026-01-01" # recent content
```

**Content audit template:**
```markdown
## Content Strategy: {competitor.com}

### Publishing Cadence
- Posts per month: X
- Content types: Blog / Case Study / Guide / Tool

### Content Pillars
1. {Topic cluster 1} — X articles
2. {Topic cluster 2} — X articles
3. {Topic cluster 3} — X articles

### Content Quality Indicators
- Avg word count: X
- Schema markup: Yes/No
- Internal linking density: X links/post
- External citations: X per post
- Multimedia: Images / Videos / Infographics
```

### 5. Technical SEO Comparison

```bash
# Page speed comparison
open "https://pagespeed.web.dev/analysis?url={competitor.com}"

# Mobile-friendly test
open "https://search.google.com/test/mobile-friendly?url={competitor.com}"

# Schema markup check
curl -sL "https://{competitor.com}" | grep -c "application/ld+json"
```

**Technical SEO scorecard:**
```markdown
| Factor | Your Site | Competitor A | Competitor B |
|--------|-----------|-------------|-------------|
| Page Speed (mobile) | X/100 | X/100 | X/100 |
| Core Web Vitals | Pass/Fail | Pass/Fail | Pass/Fail |
| Mobile Friendly | ✅/❌ | ✅/❌ | ✅/❌ |
| HTTPS | ✅/❌ | ✅/❌ | ✅/❌ |
| Schema Types | X | X | X |
| Sitemap | ✅/❌ | ✅/❌ | ✅/❌ |
| robots.txt | ✅/❌ | ✅/❌ | ✅/❌ |
| Canonical Tags | ✅/❌ | ✅/❌ | ✅/❌ |
```

### 6. SERP Share Analysis

**Calculate SERP visibility share:**
```
For each target keyword:
1. Check positions of all competitors
2. Calculate Click-Through Rate (CTR) by position
3. Multiply by search volume = estimated traffic

Position CTR estimates:
#1: 31.7% | #2: 24.7% | #3: 18.6% | #4: 13.3% | #5: 9.5%
#6: 6.3%  | #7: 4.2%  | #8: 3.1%  | #9: 2.4%  | #10: 1.8%
```

## Workflow

1. **Identify**: List 3-5 main SEO competitors
2. **Keywords**: Run keyword gap analysis
3. **Backlinks**: Compare backlink profiles
4. **Content**: Audit content strategies
5. **Technical**: Benchmark technical SEO
6. **Report**: Generate competitive intelligence report
7. **Strategy**: Create action plan to outrank competitors

## Output: Competitive Intelligence Report

```markdown
# SEO Competitive Intelligence Report

## Executive Summary
{1-paragraph overview of competitive landscape}

## Competitor Rankings
| Competitor | Keyword Overlap | Content Volume | Domain Strength | Threat Level |
|-----------|----------------|----------------|-----------------|-------------|
| {comp1} | X% | X pages | DR X | 🔴 High |
| {comp2} | X% | X pages | DR X | 🟡 Medium |

## Key Findings
1. {Biggest competitor advantage}
2. {Biggest gap/opportunity}
3. {Quick win available}

## Recommended Strategy
### Quick Wins (1-2 weeks)
- ...
### Medium-term (1-3 months)
- ...
### Long-term (3-6 months)
- ...
```

## Trigger Words
- "竞品SEO分析"
- "competitor SEO"
- "SEO gap analysis"
- "关键词差距"
- "外链对比"
- "竞争对手分析"
- "SEO competitive intelligence"
- "backlink comparison"
