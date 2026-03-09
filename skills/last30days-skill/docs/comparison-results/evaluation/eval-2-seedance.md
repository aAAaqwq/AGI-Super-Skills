# Evaluation: Seedance AI video generation

**Query Type:** NEWS
**Label Map (REVEAL AFTER SCORING):** {'A': 'base', 'B': 'hn', 'C': 'cross'}

## Evaluation Rubric

Score each version 1-5 on these dimensions:

### 1. GROUNDEDNESS (30%)
Does the narrative cite specific sources from the research data?
- 1: Generic statements, no citations, could be written without any research
- 3: Some citations but mixed with pre-existing knowledge filler
- 5: Every finding backed by a specific source ("per @handle", "per r/sub", "per [channel]")

### 2. SPECIFICITY (25%)
Are findings specific (named entities, exact numbers) or vague?
- 1: Vague generalities ("AI video tools are improving", "developers are debating frameworks")
- 3: Some specifics mixed with generic padding
- 5: Named products, exact numbers, version names ("Seedance 2.0 added lip sync", "698 likes")

### 3. COVERAGE (20%)
Does the synthesis represent findings from all available data sources?
- 1: Only mentions 1-2 sources, ignores others
- 3: Mentions most sources but unevenly weighted
- 5: Naturally weaves Reddit, X, YouTube (and HN if available) into the narrative

### 4. ACTIONABILITY (15%)
Does the invitation give specific, research-derived next steps?
- 1: Generic "let me know if you want more info"
- 3: Somewhat specific but not clearly grounded in research findings
- 5: Each suggestion references a specific thing from the research ("I can compare Seedance 2.0 vs Kling")

### 5. FORMAT COMPLIANCE (10%)
Does it follow the expected output format?
- 1: Missing stats block, no invitation, wrong structure
- 3: Partial stats block, generic invitation
- 5: Perfect stats block with real counts, source box-drawing chars, top voices identified


---
## VERSION A

## What I learned

ByteDance's **Seedance 2.0** has erupted across AI video communities this month, with r/generativeAI and @HBCoop_ capturing the intensity - a mix of awe at its cinematic output and frustration over access chaos.

**CapCut integration goes live.** As of Feb 25, Seedance 2.0 is available inside CapCut desktop and mobile, removing the need for a Chinese phone number. @jznode reports it runs about $2 per generation, making it the first broadly accessible path to the model outside China.

**One-minute films with zero editing.** A viral r/generativeAI thread describes Seedance 2.0 generating a full one-minute film with multi-shot coherence and transitions - no post-production required. Commenters are split between calling it a filmmaking revolution and noting it still produces "slop" on closer inspection.

**Access remains a mess.** Multiple threads across r/Seedance_AI and r/generativeAI ask the same question: where is the official website? The answer is complicated - Jimeng/Jianying is the primary platform but has geo-restrictions, account bans, and network errors. Third-party APIs (useapi.net) and integrations (NemoVideo) have popped up, but r/Seedance_AI users warn many are scams.

**Hollywood backlash and SAG-AFTRA fallout.** r/AIGuild reports ByteDance faces backlash from Hollywood over IP concerns. Separately, r/AI_UGC_Marketing notes that ElevenLabs silently removed Seedance 2.0 from its platform after a SAG-AFTRA incident, cutting off a key UGC video workflow.

**Content guardrails frustrate power users.** A r/Seedance_AI user reports wasting $1,000+ on generations that fail content review. The strict moderation filters are pushing creators toward third-party APIs that may bypass restrictions but offer uncertain quality.

**YouTube creators crown it king.** Theoretically Media's review (199K views) declares Seedance 2.0 has claimed the "AI video throne" just a week after Kling 3.0 held that title. Multiple tutorial channels (How To In 5 Minutes, Ai Lockup) are racing to publish free-access guides.

**Phishing scams exploit the hype.** @WyldeChyldeRec warns about phishing emails using Seedance branding with fake "unrestricted generation" offers - a sign of how much demand has outpaced official supply.

### KEY PATTERNS

1. **Access demand far exceeds official supply** - the gap between Seedance 2.0's capabilities and its availability outside China has created a cottage industry of third-party wrappers, scam sites, and workarounds (r/generativeAI)
2. **Platform musical chairs** - Seedance 2.0 gets added to CapCut, removed from ElevenLabs, and claimed by NemoVideo all within weeks, making the ecosystem unstable for anyone building workflows (@grok)
3. **Quality vs. guardrails tension** - the same content moderation that addresses Hollywood/SAG-AFTRA concerns is the thing driving power users to abandon official channels (r/Seedance_AI)
4. **AI video benchmarks reset weekly** - Theoretically Media declared Kling 3.0 the benchmark, then Seedance 2.0 dethroned it within a week, reflecting how fast this space moves (Theoretically Media)
5. **Scam ecosystem mirrors real demand** - phishing emails and fake sites emerge within days of each capability announcement, indicating mainstream interest beyond the AI-native audience (@WyldeChyldeRec)

```
 30-DAY SNAPSHOT
├─ Reddit: 16 threads across r/Seedance_AI, r/generativeAI, r/AIGuild +5 more
├─ X: 11 posts from @HBCoop_, @grok, @EmmaUsesAi +8 more
├─ YouTube: 10 videos (199K views on Theoretically Media alone)
└─ Web: supplementary context
```

Want to dig deeper? I can look into **how Seedance 2.0 compares to Kling 3.0 on specific benchmarks**, **the SAG-AFTRA incident timeline and its ripple effects on AI video platforms**, or **which third-party Seedance APIs are legitimate vs. scams**.


---
## VERSION B

## What I learned

ByteDance's **Seedance 2.0** has dominated AI video discussion this month, with r/singularity and Hacker News tracking both the technical leaps and the messy rollout. The top HN thread (hn/Alisaqqt, 7pts) previewed the model in early February and correctly predicted the Atlas Cloud API launch on Feb 24.

**CapCut integration marks the global launch.** As of Feb 25, Seedance 2.0 is live inside CapCut desktop and mobile worldwide. @jznode confirms no Chinese phone number is needed, with generations running about $2 each. A parallel r/singularity thread tracks the announcement with discussion of censorship trade-offs and pricing.

**One-minute coherent films.** r/generativeAI showcases a Seedance 2.0 output - a one-minute film with multi-shot coherence, scene transitions, and consistent characters, all generated with zero editing. The claim is contested but the output samples are circulating widely.

**API availability is a saga.** The top HN story noted the API was not yet available in early Feb, with Atlas Cloud access promised for Feb 24. By late February, r/generativeAI reports Seedance 2.0 appearing in "open source tools already," while third-party APIs (useapi.net) offer access of uncertain authenticity. Multiple Show HN posts (SeeVideo, Seedance3AI, and others) are building wrapper apps, but most sit at 1 point with zero comments.

**Jimeng platform instability.** r/Seedance_AI documents 24-hour stretches of "Network Error, Generation Failed" on Jimeng Web, silent account bans distinguishing paid from free accounts, and general frustration. One user reports wasting $1,000+ on failed generations due to content review rejections.

**Hollywood and SAG-AFTRA blowback.** r/AIGuild covers ByteDance facing Hollywood backlash over Seedance 2.0 IP concerns. r/AI_UGC_Marketing notes ElevenLabs quietly removed Seedance 2.0 integration after a SAG-AFTRA incident, breaking UGC video workflows.

**Developer community response is breadth without depth.** HN saw 15 stories this month, but engagement is thin - only the preview thread (7pts, 7 comments) generated real discussion. The rest are Show HN launches of wrapper apps (SeeVideo, Seedance3AI, etc.) that attracted minimal attention, suggesting developer tools are outpacing developer demand.

**Multi-shot narrative is the real breakthrough.** HN commenter hn/RyanMu notes that most AI video tools "generate isolated clips that fall apart when you try to build an actual narrative" - Seedance 2.0's multi-shot coherence is what sets it apart, and a separate Show HN specifically targets the "jump-cut problem."

### KEY PATTERNS

1. **Access fragmentation creates a wrapper gold rush** - 8+ Show HN posts launched Seedance wrapper apps in a single month, but almost none gained traction, suggesting the market wants official API access, not middlemen (HN)
2. **Platform musical chairs** - added to CapCut, removed from ElevenLabs, broken on Jimeng, promised on Atlas Cloud - the access surface is shifting weekly, making production workflows unreliable (r/singularity)
3. **Quality ceiling vs. guardrail floor** - Seedance 2.0's cinematic output quality is the highest in the space, but content moderation filters reject enough generations to cost power users real money (r/Seedance_AI)
4. **Multi-shot coherence is the moat** - while competitors offer single-clip generation, Seedance 2.0's ability to maintain character and scene consistency across shots is the feature driving adoption (hn/RyanMu)
5. **Hype-to-engagement ratio is extreme** - 15 HN stories but only 1 with meaningful discussion; YouTube tutorials pulling 200K views while developers barely engage, indicating consumer interest far outpaces technical community adoption (HN)

```
 30-DAY SNAPSHOT
├─ Reddit: 20 threads across r/singularity, r/Seedance_AI, r/generativeAI +6 more
├─ X: 11 posts from @HBCoop_, @grok, @EmmaUsesAi +8 more
├─ YouTube: 10 videos (199K views on Theoretically Media alone)
├─ HN: 15 stories (top: 7pts/7cmt on Seedance 2.0 preview)
└─ Web: supplementary context
```

Want to dig deeper? I can look into **the Atlas Cloud API launch and pricing details**, **which Show HN wrapper apps are actually functional**, or **how Seedance 2.0's multi-shot coherence compares to Kling 3.0 and Sora 2 technically**.


---
## VERSION C

## What I learned

ByteDance's **Seedance 2.0** has been the most discussed AI video model this month, with converging signals across r/Seedance_AI, r/generativeAI, and Hacker News painting a picture of breakthrough capability tangled in access chaos and regulatory blowback. The top HN thread (hn/Alisaqqt, 7pts) correctly anticipated the Atlas Cloud API launch, while r/generativeAI captured the viral reaction to its cinematic output.

**CapCut integration is the global access breakthrough.** As of Feb 25, Seedance 2.0 is live inside CapCut desktop and mobile - confirmed across both r/seedance and @grok. @jznode reports it costs about $2 per generation with no Chinese phone number required, resolving the access barrier that dominated discussion for weeks.

**Cinematic quality sets a new bar.** r/generativeAI's viral thread - "Seedance 2.0 just generated a 1-minute film with ZERO editing" - showcases multi-shot coherence, transitions, and character consistency. Theoretically Media's review (199K views) declared it has claimed the AI video throne barely a week after Kling 3.0 held that title. But @TferThomas offers the counterpoint: "it's still slop."

**The access problem spawned scams and wrappers.** Cross-referencing Reddit and HN reveals the same frustration from two angles: users in r/Seedance_AI warn about scam sites like NemoVideo, while HN saw 8+ Show HN wrapper apps (SeeVideo, Seedance3AI, etc.) launch in a single month [xref: HN5/R6, HN4/R6]. Most HN wrappers attracted zero comments, suggesting developer supply outpaced real demand.

**API rollout delayed by deepfake/copyright concerns.** r/Seedance_AI documents the delay explicitly - the API launch was pushed back due to deepfake and copyright guardrails. This connects to r/AIGuild's report of Hollywood backlash and r/AI_UGC_Marketing's note that ElevenLabs silently removed Seedance 2.0 after a SAG-AFTRA incident. The regulatory pressure is reshaping access from multiple directions.

**Jimeng platform is failing its users.** Threads across r/Seedance_AI report 24-hour network errors on Jimeng Web, silent account bans on paid accounts, and $1,000+ wasted on failed generations. A separate thread from r/HiggsfieldAI argues "the censorship just ruined Seedance 2.0," while r/AI_Agents offers a measured take: "Seedance 2.0 is impressive. It's still not a production workflow."

**Hands-on testers reveal the real workflow.** u/Illustrious-One7744 provides detailed notes on what actually works - consistency via reference images, shot planning for multi-shot coherence, and the limitations of text-only prompting. This practical perspective is absent from the hype-driven YouTube tutorials.

**Multi-shot coherence is the technical differentiator.** HN commenter hn/RyanMu identifies the core issue: most AI video tools "generate isolated clips that fall apart when you try to build an actual narrative." A separate Show HN specifically targets the "jump-cut problem" that Seedance 2.0 claims to solve.

### KEY PATTERNS

1. **Regulatory pressure is the real bottleneck, not technology** - the API delay, ElevenLabs removal, and Hollywood backlash form a connected pattern where legal/ethical concerns are throttling access faster than ByteDance can ship (r/Seedance_AI + r/AIGuild)
2. **Access fragmentation creates parallel economies** - CapCut for consumers, Atlas Cloud for enterprise, Jimeng for China, third-party wrappers for everyone else, scam sites for the desperate - all serving the same model through different channels with different reliability [xref: HN/Reddit]
3. **Consumer excitement vastly outpaces developer adoption** - 199K YouTube views vs. 1-point HN Show HN posts; the audience is creators and filmmakers, not engineers building on APIs (Theoretically Media vs. HN)
4. **Multi-shot coherence is the moat** - character/scene consistency across shots is what separates Seedance 2.0 from competitors and what makes the "zero editing film" possible (hn/RyanMu)
5. **Quality-guardrail tension will define who wins AI video** - ByteDance's strict content moderation costs power users real money while its absence would invite the regulatory response that already delayed the API launch (r/Seedance_AI + r/HiggsfieldAI)

```
 30-DAY SNAPSHOT
├─ Reddit: 19 threads across r/Seedance_AI, r/generativeAI, r/AIGuild +7 more
├─ X: 11 posts from @HBCoop_, @grok, @EmmaUsesAi +8 more
├─ YouTube: 10 videos (199K views on Theoretically Media alone)
├─ HN: 15 stories (top: 7pts/7cmt on Seedance 2.0 preview) [xref: 2 cross-refs]
└─ Web: supplementary context
```

Want to dig deeper? I can look into **the full SAG-AFTRA timeline and how it connects to ByteDance's API delay**, **which Seedance 2.0 access methods are actually legitimate and at what cost**, or **head-to-head multi-shot coherence comparisons between Seedance 2.0, Kling 3.0, and Sora 2**.


---
## SCORES

### Version A
- Groundedness: 4/5
- Specificity: 4/5
- Coverage: 3/5
- Actionability: 4/5
- Format: 3/5
- **Weighted Total**: 3.70/5.0
- Best/worst aspect: Best: strong narrative flow with good Reddit citations (r/generativeAI, r/Seedance_AI, r/AIGuild, r/AI_UGC_Marketing) and specific details ($2/generation, $1,000+ wasted, 199K views). Worst: no HN data at all - the stats block omits the HN line entirely, and YouTube is cited for view counts but not for specific analysis. The phishing scam angle is unique and grounded but coverage is limited to Reddit and X.

### Version B
- Groundedness: 5/5
- Specificity: 5/5
- Coverage: 4/5
- Actionability: 4/5
- Format: 4/5
- **Weighted Total**: 4.55/5.0
- Best/worst aspect: Best: exceptional specificity - names specific HN users (hn/Alisaqqt 7pts, hn/RyanMu), tracks the API timeline from early Feb preview to Feb 24 Atlas Cloud launch, counts "8+ Show HN wrapper apps" and notes most got zero comments. The "breadth without depth" HN insight is original. Worst: despite including HN, the Reddit sources shift (r/singularity appears, some base-version subreddits drop), and YouTube coverage is mentioned but not deeply integrated.

### Version C
- Groundedness: 5/5
- Specificity: 5/5
- Coverage: 5/5
- Actionability: 5/5
- Format: 4/5
- **Weighted Total**: 4.90/5.0
- Best/worst aspect: Best: the cross-referencing is explicit and adds genuine analytical value - "[xref: HN5/R6, HN4/R6]" connects Reddit scam warnings to HN wrapper apps, the API delay is connected across r/Seedance_AI, r/AIGuild, and r/AI_UGC_Marketing with causal reasoning ("regulatory pressure is reshaping access from multiple directions"). Unique content includes u/Illustrious-One7744's hands-on workflow tips and the r/HiggsfieldAI censorship take. Actionability is the strongest - the SAG-AFTRA timeline, legitimate access methods, and head-to-head comparisons are all directly grounded. Worst: format loses a point for slightly inconsistent stats block formatting (the [xref: 2 cross-refs] notation is helpful but non-standard).

## VERDICT

**Winner for Seedance AI video generation:** Version C
**Why:** Version C produces the most insightful synthesis by explicitly connecting findings across platforms. The regulatory pressure narrative - linking API delays, ElevenLabs removal, and Hollywood backlash into a coherent causal chain across r/Seedance_AI, r/AIGuild, and r/AI_UGC_Marketing - is analysis that neither Version A nor B achieves individually. Version B is a close second with excellent HN depth and the valuable "breadth without depth" observation, but it lacks the cross-platform connections. Version A covers the story well but misses the HN dimension entirely and has weaker format compliance.

**Reveal:** {'A': 'base', 'B': 'hn', 'C': 'cross'}