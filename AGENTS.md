# Contributor and coding-agent entrypoint

Before changing this repository:

1. Read [`CONTEXT.md`](./CONTEXT.md) for shared domain and architecture language.
2. Read [`ARCHITECTURE.md`](./ARCHITECTURE.md) for Modules, authority, generated outputs, Adapters, and change routes.
3. Read [`CONTRIBUTING.md`](./CONTRIBUTING.md) and the relevant decision in [`docs/adr/`](./docs/adr/).
4. Treat [`config/repository-architecture.json`](./config/repository-architecture.json) as the path-ownership contract.

Do not edit generated `catalog/` files by hand. Change their authored inputs and run `npm run build:skills`. Do not present a tracked skill, manifest, or distribution package as runtime-verified without a commit-matched receipt.

Before handing off changes, run the relevant focused tests and then:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --requirement requirements-dev.txt
npm test
npm run validate:strict
npm run check:architecture
git diff --check
```

Preserve unrelated worktree changes. Never publish, merge, deploy, or send external messages unless the user explicitly authorizes that action.
