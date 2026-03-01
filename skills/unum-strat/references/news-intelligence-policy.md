# News Intelligence Policy

## Goal

Give the agent a generic, portable way to decide:
- what sources to watch
- how to collect them
- what role they play in the strategy
- how much trust to assign them

## Source classes

### Class A - Primary
Examples:
- exchange status / incident pages
- issuer filings
- central banks
- regulators
- official project announcements
- broker notices

Use for:
- direct risk veto
- rule changes
- venue incidents
- official events

### Class B - High-quality secondary
Examples:
- major financial press
- sector publications
- reputable research desks

Use for:
- synthesis
- context
- cross-checking

### Class C - Specialist community / social
Examples:
- curated X lists
- curated Reddit communities
- selected analysts
- selected builders or desks

Use for:
- idea discovery
- anomaly detection
- early warning that must be verified elsewhere

### Class D - Trend / popularity
Examples:
- Google Trends
- search-intent changes
- tag frequency
- keyword spikes

Use for:
- demand / attention context
- prioritization
- regime color

Never use Class C or D alone as final trade justification.

## Query design

For each venue or asset, define:
- keywords
- exclusions
- whitelists
- refresh cadence
- escalation rules

### Example fields
- topic
- source class
- query string
- include terms
- exclude terms
- freshness window
- escalation target
- action role: trigger / filter / veto / monitor / research-only

## Collection methods

### web_search
Use first for:
- discovery
- recency checks
- broad scanning
- monitoring specific query buckets

### web_fetch
Use for:
- article text extraction
- official pages
- readable summaries
- lower-friction structured ingest

### browser
Use only when needed:
- JS-heavy sites
- interactive pages
- login-protected pages
- screenshot verification

### cron or scheduled scans
Use for:
- recurring monitoring
- digest generation
- pre-market / pre-session checks
- high-priority venue and incident scans

## Generic escalation ladder

1. detect something from search, social, or trend data
2. verify with a primary or high-quality secondary source
3. decide whether it is:
   - a veto
   - a filter
   - a research note
   - irrelevant noise
4. log the decision
5. expire stale stories and deduplicate repeats

## Good generic query buckets

- listing / delisting / halt / maintenance / outage
- funding / borrow / margin / fee / custody change
- ETF / filing / guidance / earnings / buyback / split
- exploit / depeg / governance vote / fork / liquidation
- macro release / rate decision / CPI / payroll / sanctions / war escalation

## Risk controls

- cap the number of social-only items promoted to review
- require primary-source confirmation for any trade-impacting alert
- maintain per-source trust levels
- keep a stale-news cutoff
- record whether a source has historically been noisy
