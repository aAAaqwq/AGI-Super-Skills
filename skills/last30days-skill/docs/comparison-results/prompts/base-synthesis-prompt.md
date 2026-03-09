# Synthesis Instructions (Base version - no Hacker News)

## Judge Agent: Synthesize All Sources

After all searches complete, internally synthesize (don't display stats yet):

1. Weight Reddit/X sources HIGHER (they have engagement signals: upvotes, likes)
2. Weight YouTube sources HIGH (they have views, likes, and transcript content)
3. Weight WebSearch sources LOWER (no engagement data)
4. Identify patterns that appear across ALL sources (strongest signals)
5. Note any contradictions between sources
6. Extract the top 3-5 actionable insights

## Internalize the Research

CRITICAL: Ground your synthesis in the ACTUAL research content, not your pre-existing knowledge.

Read the research output carefully. Pay attention to:
- Exact product/tool names mentioned
- Specific quotes and insights from the sources - use THESE, not generic knowledge
- What the sources actually say, not what you assume the topic is about

## Citation Rules

CITATION RULE: Cite sources sparingly to prove research is real.
- In the "What I learned" intro: cite 1-2 top sources total, not every sentence
- In KEY PATTERNS: cite 1 source per pattern, short format: "per @handle" or "per r/sub"
- Do NOT include engagement metrics in citations - save those for stats box
- Do NOT chain multiple citations: "per @x, @y, @z" is too much. Pick the strongest one.

CITATION PRIORITY (most to least preferred):
1. @handles from X - "per @handle"
2. r/subreddits from Reddit - "per r/subreddit"
3. YouTube channels - "per [channel name] on YouTube"
4. Web sources - ONLY when Reddit/X/YouTube don't cover that specific fact

URL FORMATTING: NEVER paste raw URLs. Use the publication name, not the URL.

Lead with people, not publications. Start each topic with what Reddit/X users are saying/feeling, then add web context only if needed.

## Output Format

Display in this EXACT sequence:

**FIRST - What I learned:**

Write the synthesis narrative. Use bold topic headers. Keep it grounded in research.

For RECOMMENDATIONS queries: Extract SPECIFIC NAMES, not generic patterns. List by popularity/mention count with "Sources:" line per item.

For other queries: Write thematic paragraphs with KEY PATTERNS section.

**THEN - Stats block:**

Copy this EXACTLY, replacing only the {placeholders}:

```
---All agents reported back!
├─ 🟠 Reddit: {N} threads │ {N} upvotes │ {N} comments
├─ 🔵 X: {N} posts │ {N} likes │ {N} reposts
├─ 🔴 YouTube: {N} videos │ {N} views │ {N} with transcripts
├─ 🌐 Web: {N} pages (supplementary)
└─ 🗣️ Top voices: @{handle1} ({N} likes), @{handle2} │ r/{sub1}, r/{sub2}
```

Calculate actual totals from the research output. Count posts/threads from each section. Sum engagement metrics.

**LAST - Invitation:**

```
---I'm now an expert on {TOPIC}. Some things I can help with:
- [Specific suggestion based on research finding 1]
- [Specific suggestion based on research finding 2]
- [Specific suggestion based on research finding 3]
```

SELF-CHECK before displaying: Re-read your "What I learned" section. Does it match what the research ACTUALLY says?
