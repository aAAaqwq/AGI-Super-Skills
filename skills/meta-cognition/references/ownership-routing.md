# Ownership Routing

Use this reference when deciding who should own a task.

## Routing principle

Assign by **core capability**, not by who is currently active or convenient.

## Default mapping

| Capability | Primary owner | Typical outputs |
|---|---|---|
| OpenClaw ops, gateway, cron, monitoring, logs | ops | config fixes, cron changes, root-cause notes |
| Code, scripts, backend/frontend, deployment setup | code | code changes, tests, implementation notes |
| Market/trading strategy, positions, Polymarket | quant | market analysis, strategy recommendations, execution checks |
| Data collection, scraping, cleaning, pipelines | data | datasets, scrapers, analysis tables |
| Research, external landscape, technical investigation | research | reports, comparisons, source-backed analysis |
| Writing, content adaptation, style polishing | content | drafts, rewrites, platform-specific copy |
| PM, task breakdown, acceptance criteria | pm | PRD, task lists, acceptance checklists |
| Finance, ROI, P&L, cost accounting | finance | cost tables, ROI analysis, summaries |
| Marketing/growth/channel strategy | market | growth plans, distribution strategy |
| Legal/compliance | law | legal risk notes, policy review |
| Product framing / design direction | product | design judgments, positioning |
| Outreach / sales targeting | sales | lead analysis, prospecting plans |

## CEO rule

The CEO/main session should usually:
- frame the task
- choose the owner
- decide escalation
- review quality
- report the final decision

The CEO/main session should usually **not** do specialist execution if a dedicated agent exists.

## Parallelism rule

Use parallel dispatch when:
- sub-tasks are independent
- owners differ by capability
- waiting sequentially adds no value

Examples:
- research gathers landscape while pm drafts scope
- data extracts samples while code prepares API skeleton
- ops checks runtime health while quant validates trading implications

Do not force parallelism when one output is required to start the next.

## Routing questions

Before dispatching, answer:
1. What is the core capability?
2. Which agent has that as primary responsibility?
3. What exact deliverable is expected?
4. Does the agent need context, files, or a specific format?
5. How will we know the task is actually complete?
