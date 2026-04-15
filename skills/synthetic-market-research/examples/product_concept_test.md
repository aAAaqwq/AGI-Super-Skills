# Example: SaaS Concept Test

## Research Question
"Would B2B sales teams pay for an AI tool that automatically researches prospects and writes personalized outreach messages?"

## Concept Description
**ProspectAI** — An AI-powered sales tool that monitors job boards, LinkedIn, and company news to identify prospects matching your ICP. It researches each prospect, finds relevant talking points, and drafts personalized cold emails. $49/month per seat.

## Personas

| # | Age | Income | Location | Profile |
|---|-----|--------|----------|---------|
| 1 | 28 | $65K | San Francisco | SDR at a Series B startup, cold-emails 50+ prospects/day, tech-savvy |
| 2 | 35 | $120K | Chicago | VP Sales at a mid-market SaaS company, manages a team of 8 SDRs |
| 3 | 42 | $95K | Austin | Solo founder doing their own sales, bootstrapped B2B tool |
| 4 | 24 | $45K | New York | Recent grad in first BDR role, learning sales process |
| 5 | 52 | $150K | Boston | Enterprise sales director, complex deal cycles, values relationships |
| 6 | 31 | $80K | Denver | Account executive at a growing startup, does own prospecting |

## Generated Responses

**Persona 1 (SDR, 28, SF):**
> "This is exactly what I need. I spend 2-3 hours every morning just researching prospects on LinkedIn before I can even start writing emails. If this tool could cut that down and actually write decent first drafts, $49/month is nothing — my company would pay that in a heartbeat. My only concern is whether the personalization is actually good or if it sounds like every other AI-generated email that prospects immediately delete."

**Persona 2 (VP Sales, 35, Chicago):**
> "Interesting concept. For my team of 8 SDRs, that's about $400/month which is reasonable if it actually improves reply rates. I've tried similar tools before and the research quality was mediocre — generic stuff anyone could find in 30 seconds. If ProspectAI can surface non-obvious insights like recent company moves or personal interests, I'd pilot it. But I'd need to see a meaningful lift in reply rates within the first month or I'm canceling."

**Persona 3 (Solo founder, 42, Austin):**
> "As a bootstrapped founder, every dollar matters, but $49/month for something that saves me hours of research time is a no-brainer IF it works. I've been burned by AI tools that promise personalization but deliver template-sounding messages. I'd want a free trial to validate the quality before committing. The prospect research part interests me more than the email writing — I prefer writing in my own voice."

**Persona 4 (BDR, 24, NYC):**
> "I'd definitely want to try this, but I'm not sure my manager would approve another tool subscription. We already use ZoomInfo and Outreach. Would this integrate with those? The automatic research part sounds great for learning about prospects faster, but I worry about becoming too dependent on AI and not developing my own research skills early in my career."

**Persona 5 (Enterprise, 52, Boston):**
> "In enterprise sales, relationships matter more than volume. I don't send cold emails — I work warm introductions and strategic account plans. This tool seems designed for high-volume outbound which isn't my world. That said, the research component could be useful for account intelligence. But at $49/seat I'd expect it to integrate deeply with Salesforce and provide account-level insights, not just individual prospect research."

**Persona 6 (AE, 31, Denver):**
> "I'd probably try this. My biggest pain point is the time between getting a new account assigned and actually understanding enough about the prospect to have a meaningful conversation. If ProspectAI can give me a solid brief in minutes instead of the hour I currently spend, that's valuable. The email drafting is secondary — I'd mainly use it for research. Price seems fair for what it offers."

## SSR Results

### Per-Persona PMFs

| Persona | P(1) | P(2) | P(3) | P(4) | P(5) | E[score] |
|---------|------|------|------|------|------|----------|
| 1 (SDR, 28) | 0.02 | 0.05 | 0.12 | 0.38 | 0.43 | 4.15 |
| 2 (VP Sales, 35) | 0.03 | 0.08 | 0.25 | 0.40 | 0.24 | 3.74 |
| 3 (Solo founder, 42) | 0.02 | 0.06 | 0.18 | 0.42 | 0.32 | 3.96 |
| 4 (BDR, 24) | 0.04 | 0.12 | 0.30 | 0.35 | 0.19 | 3.53 |
| 5 (Enterprise, 52) | 0.10 | 0.22 | 0.35 | 0.25 | 0.08 | 2.99 |
| 6 (AE, 31) | 0.03 | 0.07 | 0.22 | 0.40 | 0.28 | 3.83 |

### Overall Survey PMF

| Definitely not (1) | Probably not (2) | Maybe (3) | Probably (4) | Definitely (5) |
|-----|------|------|------|------|
| 0.04 | 0.10 | 0.24 | 0.37 | 0.26 |

**Mean Purchase Intent: 3.70 / 5.00**

### Segment Analysis

**By Age:**
- Under 35 (Personas 1, 4, 6): Mean = 3.84 — Younger sales professionals see more value
- 35-45 (Personas 2, 3): Mean = 3.85 — Mid-career sees clear ROI case
- Over 50 (Persona 5): Mean = 2.99 — Enterprise sales has different workflow, weaker fit

**By Income:**
- Under $70K (Personas 1, 4): Mean = 3.84 — IC contributors want efficiency gains
- $70K-$120K (Personas 2, 3, 6): Mean = 3.84 — Mid-level willing to pay for time savings
- Over $120K (Persona 5): Mean = 2.99 — Senior enterprise sees limited fit

### Qualitative Themes

1. **Research > Writing**: 4/6 personas valued the prospect research more than email drafting. Consider positioning research as the primary value prop.
2. **Quality skepticism**: 3/6 mentioned concerns about AI-generated content quality, having been burned by similar tools. Social proof and free trials are critical.
3. **Integration expectations**: 2/6 mentioned needing integration with existing tools (Salesforce, Outreach, ZoomInfo). Standalone tools face adoption friction.
4. **Pricing is acceptable**: No persona flagged $49/seat as too expensive. The price-value equation works for the SMB/mid-market segment.
5. **Enterprise is a weak segment**: The enterprise sales director saw minimal fit. Consider focusing GTM on SMB/mid-market high-volume outbound teams.

### Recommendations

1. **Lead with research, not writing** — Position as "AI prospect intelligence" rather than "AI email writer"
2. **Free trial is essential** — Quality skepticism is the #1 barrier; let the product speak for itself
3. **Target SMB/mid-market SDR teams** — Strongest signal from high-volume outbound personas
4. **Deprioritize enterprise** — Different workflow, different value prop, likely needs separate positioning
5. **Build integrations early** — CRM and sales engagement tool integrations reduce adoption friction

### Limitations

- Synthetic responses from 6 personas — real validation with 20+ actual SDRs/AEs recommended before launch decisions
- U.S.-centric personas — international markets may have different dynamics
- Price sensitivity not deeply tested — consider running a dedicated pricing study with the comparative mode
