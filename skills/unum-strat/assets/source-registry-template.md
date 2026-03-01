# Source Registry Template

Use this template to define what the agent should read.

| Topic | Asset / Venue Scope | Source Name | Class | Trust | Method | Query / Path | Cadence | Role |
|---|---|---|---|---|---|---|---|---|
| Exchange status | Crypto venue | Official status page | A | High | web_fetch / browser | status OR incident page | 5-15m | veto |
| Delisting / listing | Venue | Official announcements | A | High | web_search + fetch | listing OR delisting | 30-60m | filter |
| Macro releases | Multi-asset | Official release source | A | High | web_search + fetch | CPI OR rates OR payrolls | scheduled | veto/filter |
| Sector news | Any | Reputable press | B | Med-High | web_search + fetch | tailored queries | 30-120m | context |
| Social anomaly | Any | Curated X list | C | Medium | browser or API path outside skill | custom list / tags | 15-60m | escalate |
| Trend signal | Any | Search / tag trend | D | Low-Med | external trend source | keyword set | daily / hourly | monitor |

## Notes
- Keep Class C and D as escalation layers, not final authority.
- Add exclusions to avoid spam and duplicates.
- Record which sources are noisy.
