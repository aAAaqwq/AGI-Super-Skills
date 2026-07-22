# Evidence and contract tests

Tests protect repository Interfaces; they do not prove business outcomes.

| Area | Evidence |
|---|---|
| Inventory, manifest, references, workflows | repository validator tests |
| Preview, preflight, no-clobber, staging | [`installer/test_install.sh`](./installer/test_install.sh) |
| Taxonomy, generated catalog, classification details | `test_skill_catalog.py` |
| Structural skill debt | `test_skill_quality.py` |
| Modules, path ownership, authority, lineage, Adapters | `test_architecture_contracts.py` |
| README, navigation, site, SEO, cached data | readme/navigation/site/data tests |

Run focused tests while editing, then `npm test`, `npm run validate:strict`, and `git diff --check`. Runtime harness and outcome evidence remains a separate release gate.
