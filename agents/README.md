# Agent directory

This directory contains role and operating files for the generic workspace installer. The canonical roster and skill requirements live in [`config/team-manifest.json`](../config/team-manifest.json).

The installer copies files; it does not launch agents, configure a model, or make a harness load the generated workspaces automatically.

## Canonical roster

| ID | Role | Primary responsibility |
|---|---|---|
| [`ceo`](./ceo/) | CEO | Coordination, decisions, and quality gates |
| [`cto`](./cto/) | CTO | Technology strategy and architecture |
| [`pe`](./pe/) | Principal Engineer | Implementation, testing, and delivery |
| [`cpo`](./cpo/) | CPO | Product direction and user experience |
| [`cqo`](./cqo/) | CQO | Quantitative research and model evaluation |
| [`cmo`](./cmo/) | CMO | Marketing, positioning, and growth |
| [`cfo`](./cfo/) | CFO | Finance, capital allocation, and controls |
| [`cdo`](./cdo/) | CDO | Data quality, analytics, and governance |
| [`cco`](./cco/) | CCO | Content research and reviewable drafts |
| [`clo`](./clo/) | CLO | Legal reasoning and compliance review |
| [`cro`](./cro/) | CRO | Research design and evidence synthesis |
| [`cso`](./cso/) | CSO | Sales, partnerships, and revenue workflows |
| [`coo`](./coo/) | COO | Operations and cross-team execution |
| [`governor`](./governor/) | Governor | Independent challenge and escalation |

Mentor names inside persona files are creative framing. They do not imply affiliation, endorsement, or guaranteed imitation.

## Directory contract

An Agent directory may contain:

```text
agents/<id>/
├── AGENTS.md       # Operating rules and role boundaries
├── SOUL.md         # Persona and communication style
├── IDENTITY.md     # Role identity and purpose
├── BOOTSTRAP.md    # Startup reading order
├── MEMORY.md       # Versioned memory guidance
├── USER.md         # User-context template
├── WORKFLOW.md     # Role workflow and handoffs
└── TOOLS.md        # Active skill references
```

`TOOLS.md` references must resolve to tracked physical skills and match the manifest. The repository validator rejects broken or machine-local references.

## Install safely

Preview one Agent from a reviewed checkout:

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace ceo
```

Apply only after inspecting the preview:

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace --apply ceo
```

For small cross-functional selections, start with the [`solo-founder`](../starter-kits/solo-founder/), [`content-creator`](../starter-kits/content-creator/), or [`quant-trader`](../starter-kits/quant-trader/) kit.

## Verify changes

```bash
npm test
npm run validate -- --warnings-as-errors
```

See the [setup guide](../setup.md), [team roster](./TEAM_ROSTER.md), and [contribution policy](../CONTRIBUTING.md) for installation, review, and provenance requirements.
