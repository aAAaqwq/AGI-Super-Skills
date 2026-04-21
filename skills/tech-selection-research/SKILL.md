---
name: tech-selection-research
description: Use when the user wants to research, compare, or evaluate a technology, framework, platform, or engineering tool for product R&D decision-making, such as "调研 FastAPI", "技术选型", "compare Spring Boot vs NestJS", "写 ADR", "评估是否适合", "PoC 方案", or "technology radar".
allowed-tools: Bash, WebSearch, WebFetch, Read, Write, Glob, Grep
disable-model-invocation: true
context: fork
---

# Tech Selection Research

Research a technology or framework for product R&D decisions. The goal is not a generic overview. The goal is a decision-ready output with evidence, tradeoffs, ADR draft, and validation plan.

## Use This Skill For

- Researching a single technology or framework for adoption
- Comparing 2-4 candidate options for a project
- Producing an ADR draft for architecture or framework selection
- Defining a PoC plan and validation checklist
- Producing a trend update for an already adopted technology

## Do Not Do

- Do not invent benchmark numbers
- Do not recommend based only on popularity
- Do not ignore migration cost or team capability
- Do not give an absolute answer when key project constraints are missing

## Workflow

### 1. Frame The Decision

Convert "research X" into a decision statement:

- What is being chosen?
- For which product or engineering context?
- New build or brownfield migration?
- What are the hard constraints: language, cloud, compliance, hiring, timeline?

If constraints are missing, make minimal assumptions and label them explicitly.

### 2. Choose Mode

Pick the lightest mode that matches the request:

- `Quick Scan`: one technology, fast assessment
- `Shortlist Comparison`: 2-4 candidates
- `Decision Pack`: decision-ready report + ADR + PoC
- `Trend Update`: latest releases, roadmap, upgrade risks

#### Quick Scan Workflow

Skip weighted matrix and ADR. Output:

1. Technology positioning and history
2. Fit / not-fit summary for the given context
3. Radar classification: Adopt / Trial / Assess / Hold
4. Key risks (top 3-5)
5. Verdict: worth shortlisting or not, with reasoning

#### Shortlist Comparison Workflow

Use steps 1, 3, and 4 from the main workflow. Output:

1. Candidate landscape (full universe, then scored shortlist)
2. Unified dimension comparison table
3. Exclusion rationale for dropped candidates
4. Recommended shortlist with brief justification per option

#### Decision Pack Workflow

Follow the full workflow (steps 1-6). This is the default for any non-trivial selection.

> **Note**: Decision Pack consumes 40-60% of the context window (loading references, multiple WebSearch/WebFetch calls, generating a 300-400 line report). If your current session already has substantial conversation history, run `/clear` first or start a new session to avoid mid-report context compression.

#### Trend Update Workflow

Skip candidate landscape and weighted matrix. Focus on delta since last assessment. Output:

1. Recent releases, breaking changes, deprecations
2. Roadmap / RFC / proposal summary
3. Maturity change vs last assessment (radar shift)
4. Community sentiment changes or emerging concerns
5. Upgrade or replacement risks
6. Whether the current adoption decision still holds

### 3. Use Source Hierarchy

Use sources in this order:

1. Official docs, release notes, roadmap, RFCs, maintainer material
2. Foundation or standards bodies, major engineering blogs, InfoQ, Thoughtworks
3. Community tutorials only for supplemental explanation

When current information matters, verify with current sources. Distinguish:

- Verified fact
- Inference from sources
- Requires PoC or benchmark validation

For source rules and evidence labels, read `references/source-hierarchy.md`.

### 4. Evaluate On Standard Dimensions

Use the standard dimensions unless the user provides their own:

- Business fit
- Architecture fit
- Team capability fit
- Delivery speed
- Runtime and scalability
- Operability and observability
- Security and compliance
- Ecosystem maturity
- Migration cost
- Long-term evolution

Dimension definitions and scoring guidance are in `references/evaluation-framework.md`.

Before scoring, map the broader competitor universe. If the space includes multiple paradigm-level alternatives, do not compare only one or two obvious products. Make explicit:

- the full candidate universe worth mentioning
- the scored shortlist
- why some important alternatives were not fully scored

### 5. Produce Decision Outputs

Default output should contain:

1. Executive summary (include radar classification: Adopt / Trial / Assess / Hold)
2. Decision context and assumptions
3. Candidate landscape
4. Evidence-based comparison
5. Recommendation with "recommended when" and "not recommended when"
6. Risks, unknowns, and tradeoffs
7. Community negative feedback and criticism
8. Non-fit scenarios
9. Important cautions before adoption
10. PoC plan
11. ADR draft
12. Tracking plan

Output structure and ADR template are in `references/output-templates.md`.

### 6. Use The Matrix Script When Helpful

If you have structured scores, use:

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/build_decision_matrix.py" <input.json>
```

`$CLAUDE_SKILL_DIR` is set automatically by Claude Code to the skill's root directory. If running outside Claude Code, substitute the absolute path.

The script expects JSON with `weights` and `options`. See the script docstring for shape.

## Important Guardrails

- Every recommendation must include:
  - Why it fits
  - Why it may fail
  - What must be validated next
- Every performance or cost claim must cite a source or be marked `needs PoC`
- Keep alternatives visible. Do not analyze only the named tool if realistic substitutes exist
- Brownfield decisions must include migration and rollback considerations

## Language

- Top-level section headings: use English exactly as defined in the output template
- Body content and sub-headings: follow the user's input language
- Evidence labels (`Verified`, `Inference`, `Needs PoC`): always in English

## Output Location

Save the report in the current working directory with the naming pattern:
`{technology}-decision-pack-{yyyy-mm-dd}.md`

For Quick Scan, use `{technology}-quick-scan-{yyyy-mm-dd}.md`.
For Trend Update, use `{technology}-trend-update-{yyyy-mm-dd}.md`.

## Files To Read

- Read `references/evaluation-framework.md` for scoring dimensions and ATAM-style tradeoff prompts
- Read `references/source-hierarchy.md` for source priority and evidence labeling
- Read `references/output-templates.md` for the decision-pack structure, ADR template, and PoC template
