---
name: serp-analysis
description: "Analyze Google SERP (Search Engine Results Pages) — featured snippets, PAA (People Also Ask), AI Overview, knowledge panels, local packs. Detect AI Overview trigger conditions and optimize content to be cited by AI. Use when user asks to 'analyze SERP', 'check search results', 'AI Overview analysis', 'featured snippet optimization', 'PAA research', or 'how to get cited by Google AI'."
license: MIT
metadata:
  version: 1.0.0
  domains: [seo, serp, search-analysis, geo]
  type: specialist
---

# SERP Analysis Skill

Analyze and reverse-engineer Google Search Engine Results Pages to understand ranking patterns, featured snippet triggers, AI Overview conditions, and optimization opportunities.

## When to Use
- Analyzing SERP features for a keyword
- Understanding AI Overview trigger conditions
- Featured snippet optimization
- People Also Ask (PAA) research
- Competitor SERP position analysis
- Local pack analysis

## Capabilities

### 1. SERP Feature Detection
Identify all SERP features for a given query:
- **Featured Snippets** (paragraph, list, table, video)
- **AI Overview / SGE** (Google's AI-generated answers)
- **People Also Ask (PAA)** boxes
- **Knowledge Panel**
- **Local Pack** (map results)
- **Image/Video carousels**
- **Shopping results**
- **Sitelinks**

### 2. AI Overview Analysis

**How to check if AI Overview triggers:**
```bash
# Manual: Search on Google with the query
# Automated: Use SerpAPI or similar
curl -s "https://serpapi.com/search?q={query}&engine=google&api_key={key}" | python3 -c "
import json, sys
data = json.load(sys.stdin)
ai_overview = data.get('ai_overview', {})
if ai_overview:
    print('✅ AI Overview detected')
    print(f'Sources: {len(ai_overview.get(\"sources\", []))}')
    for s in ai_overview.get('sources', []):
        print(f'  - {s.get(\"title\")}: {s.get(\"link\")}')
else:
    print('❌ No AI Overview for this query')
"
```

**AI Overview trigger conditions:**
| Factor | Triggers AI Overview | Doesn't Trigger |
|--------|---------------------|-----------------|
| Query type | Informational, how-to | Navigational, exact-match |
| Complexity | Multi-step, comparison | Simple factual |
| Intent | Research, learning | Transaction, login |
| Content availability | Rich authoritative sources | Thin content |

### 3. Featured Snippet Optimization

**Snippet types and how to win them:**

| Type | Format | Optimization |
|------|--------|-------------|
| **Paragraph** | 40-60 word answer | Answer question directly in first paragraph |
| **List** | Ordered/unordered | Use H2/H3 + bullet/numbered list |
| **Table** | Data comparison | Use HTML `<table>` with clear headers |
| **Video** | YouTube embed | Timestamp chapters + transcript |

**Template for winning paragraph snippets:**
```
<h2>What is {keyword}?</h2>
<p>{Keyword} is {direct 40-60 word answer that completely addresses the query, 
including key context and a specific data point or statistic}.</p>
```

### 4. PAA (People Also Ask) Research

**Extract PAA questions for content planning:**
```bash
# Search and extract PAA
WebSearch: "{keyword}"
# Look for "People Also Ask" section
# Each PAA question = content opportunity
```

**PAA optimization checklist:**
- [ ] Answer each PAA question in your content
- [ ] Use the exact PAA question as an H2/H3
- [ ] Provide concise answer (40-60 words) immediately after heading
- [ ] Expand with details below the concise answer
- [ ] Include relevant schema markup (FAQPage)

### 5. SERP Competitive Analysis

**Analyze top 10 results:**
```markdown
| Position | URL | Title Length | Meta Desc | Schema | Word Count | Domain Authority |
|----------|-----|-------------|-----------|--------|------------|-----------------|
| 1 | ... | ... | ... | ... | ... | ... |
| 2 | ... | ... | ... | ... | ... | ... |
```

**Key metrics to compare:**
- Content length and depth
- Schema markup types used
- Backlink profile
- Content freshness (last updated date)
- Page speed score
- Mobile-friendliness

## Workflow

1. **Input**: Target keyword or URL
2. **Search**: Query Google (via web_fetch or SerpAPI)
3. **Detect**: Identify all SERP features present
4. **Analyze**: Breakdown top results' strategies
5. **Recommend**: Specific optimizations to win SERP features
6. **Report**: Structured SERP analysis report

## Output Format

```markdown
## SERP Analysis Report: "{keyword}"

### SERP Features Detected
- [ ] AI Overview: Yes/No
- [ ] Featured Snippet: Type
- [ ] PAA: X questions
- [ ] Knowledge Panel: Yes/No
- [ ] Local Pack: Yes/No
- [ ] Image Carousel: Yes/No

### Top 3 Competitors
1. {URL} — {why they rank}
2. {URL} — {why they rank}
3. {URL} — {why they rank}

### Opportunities
1. {Specific action to take}
2. {Specific action to take}
3. {Specific action to take}

### AI Overview Optimization
- Current citation status: Cited / Not cited
- Recommended changes: ...
```

## Trigger Words
- "分析搜索结果"
- "SERP analysis"
- "check SERP features"
- "AI Overview 分析"
- "featured snippet"
- "PAA 研究"
- "搜索结果页分析"
- "谷歌排名分析"
