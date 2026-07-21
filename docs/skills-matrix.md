# Legacy Agent matrix

This path is retained so old links do not break. The former hand-maintained matrix drifted from both the physical inventory and the active Agent manifest, so its assignments were removed.

Use these current sources instead:

- [Skill catalog](../catalog/) — generated task categories and support levels.
- [Machine-readable skill index](../catalog/skill-index.json) — deterministic records for search and tooling.
- [Team manifest](../config/team-manifest.json) — active Agent requirements and external recommendations.
- [Agent guide](../agents/) — role-level navigation and evidence boundaries.

Regenerate the catalog and verify the repository with:

```bash
npm run build:skills
npm test
npm run validate -- --warnings-as-errors
```
