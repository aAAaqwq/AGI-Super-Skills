# Repository implementations

Scripts are replaceable Implementations behind documented repository Interfaces.

| Responsibility | Implementation | Public check |
|---|---|---|
| Canonical repository model | [`repository_model.py`](./repository_model.py) | `npm run validate:strict` |
| Skill discovery catalog | [`build_skill_catalog.py`](./build_skill_catalog.py) | `npm run check:skills` |
| Skill structural quality | [`audit_skill_quality.py`](./audit_skill_quality.py) | `npm run check:skill-quality` |
| Architecture classification | [`audit_architecture.py`](./audit_architecture.py) | `npm run check:architecture` |
| Same-origin Pages data | [`build_site_data.py`](./build_site_data.py) | repository and site-data tests |

Do not treat a script as an authority when it merely reads one. See the [architecture registry](../config/repository-architecture.json) for ownership and generated lineage.
