<p align="center">
  <img src="assets/banner.png" alt="AGI Super Team — Evidence-backed AI teams for real outcomes" width="100%">
</p>

<h1 align="center">AGI Super Team</h1>

<p align="center"><strong>Evidence-backed AI teams for real outcomes</strong></p>

<p align="center">
  <a href="./README_CN.md">中文</a> ·
  <a href="#safe-quick-start">Quick start</a> ·
  <a href="#five-minute-installation-receipt">Receipt</a> ·
  <a href="#browse-skills-by-outcome">Skills</a> ·
  <a href="#repository-architecture">Architecture</a> ·
  <a href="./docs/guides/">Guides</a> ·
  <a href="./CONTRIBUTING.md">Contribute</a>
</p>

## What this repository is

AGI Super Team provides installable AI team packs, role instructions, and reusable skills for existing coding-agent harnesses.

It is not a model or an agent runtime. It provides versioned workspace configurations that help people plan, build, review, and communicate with explicit human approval gates.

Three constraints make the project different:

- **Inspect before write:** the generic installer previews every destination and requires explicit `--apply`.
- **One source of truth:** agents, kits, local requirements, and external recommendations come from a validated manifest.
- **Evidence before claims:** compatibility and outcomes remain pending until a receipt matches the tested revision.

Trading, legal, security, medical, publishing, and deployment work still requires qualified human review.

## Safe quick start

Using Codex? Start with the [curated native package](./.codex/INDEX.md). Evaluating generic workspace files? Continue below.

Clone `main`, record the commit you reviewed, and preview the Solo Founder pack. The installer requires Bash and Node.js; repository verification also requires npm and Python 3.

```bash
git clone --depth 1 --branch main https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team
git rev-parse HEAD
./install.sh --source "$PWD" --destination /path/to/review-workspace solo-founder
```

Review the source, destination, selected agents, and planned files. Apply only when the preview matches your intent:

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace --apply solo-founder
```

The installer preserves existing persona files and skill directories. It rejects missing required skills, source symlinks, and destination symlinks before publishing staged files.

Avoid piping a remote script into a shell when you can inspect a pinned checkout first. See [setup.md](./setup.md) for prerequisites, updates, and recovery.

### Preview → apply → verify

<p align="center">
  <img src="assets/demo-install.gif" alt="Terminal demo showing a read-only preview, explicit apply, and repository checks passing" width="760">
</p>

The animation is an illustrative storyboard with sanitized paths, not runtime evidence. Read the [storyboard transcript](./assets/demo-install.txt), then use the receipt below for reproducible commands.

## Five-minute installation receipt

The repository currently verifies a safe installation outcome. It does not yet claim that an installed team has produced a validated business result.

“Five-minute” describes the walkthrough scope, not a speed guarantee. This path evaluates the generic file installer; it does not configure a model or make a harness load generated workspaces automatically.

Create a disposable destination, prove preview wrote nothing, apply, then confirm the three expected role workspaces:

```bash
AGI_SOLO_DEST="$(mktemp -d "${TMPDIR:-/tmp}/agi-solo-founder.XXXXXX")"

./install.sh --source "$PWD" --destination "$AGI_SOLO_DEST" solo-founder
test -z "$(find "$AGI_SOLO_DEST" -mindepth 1 -print -quit)"

./install.sh --source "$PWD" --destination "$AGI_SOLO_DEST" --apply solo-founder
test -f "$AGI_SOLO_DEST/workspace-ceo/SOUL.md"
test -f "$AGI_SOLO_DEST/workspace-pe/SOUL.md"
test -f "$AGI_SOLO_DEST/workspace-cco/SOUL.md"

npm test
npm run validate -- --warnings-as-errors
```

Print and inspect `$AGI_SOLO_DEST` before moving or removing anything. A real customized destination requires its own backup and review; repeated apply is not an upgrade or rollback mechanism.

The installer stops after copying inspectable files. It does not launch agents, orchestrate roles, or create the outputs below. Use these only as optional manual prompts in a separately configured harness.

| Workspace | Responsibility | Optional evaluation prompt |
|---|---|---|
| `workspace-ceo` | Planning and quality gates | Draft a decision memo with assumptions, alternatives, evidence gaps, and a human approval gate. |
| `workspace-pe` | Engineering and delivery | Propose a test-first implementation plan. Do not deploy or change production systems. |
| `workspace-cco` | Launch communication | Draft three launch-post variants with claim placeholders and a manual publishing checklist. |

This receipt proves deterministic installation and repository integrity. Cross-harness task performance remains **Validation pending** until a public fixture is tied to the current `main` commit.

## Browse skills by outcome

Start with a focused pack or guide. The complete catalog is a reference library, not the recommended onboarding path.

| Path | Use it for |
|---|---|
| [Starter kits](./starter-kits/) | Small role combinations for a founder, content workflow, or quantitative research |
| [Agents](./agents/) | Persona, identity, workflow, and tool guidance for the generic installer |
| [Practical guides](./docs/guides/) | Codex and Claude Code setup, compatibility, team choice, and workflow boundaries |
| [Codex package](./.codex/INDEX.md) | A separately curated native package with its own manifest and sync policy |
| [Cookbooks](./cookbook/) | Longer learning material for content, prompts, research, and quantitative workflows |
| [Skills overview](./skills/) | Support levels, bounded starting points, and discovery guidance |
| [Generated skill catalog](./catalog/) | Task-oriented categories covering every canonical physical skill |

### Skill categories

| Build and operate | Reach and create | Decide and automate |
|---|---|---|
| [AI Agents & Orchestration](./catalog/#ai-agents-orchestration) | [Marketing, SEO & Growth](./catalog/#marketing-seo-growth) | [Data, Analytics & Research](./catalog/#data-analytics-research) |
| [Software Engineering](./catalog/#software-engineering) | [Content, Media & Publishing](./catalog/#content-media-publishing) | [Business Operations & Strategy](./catalog/#business-operations-strategy) |
| [Cloud, DevOps & Reliability](./catalog/#cloud-devops-reliability) | [Sales, CRM & Customer Success](./catalog/#sales-crm-customer-success) | [Apps & Workflow Automation](./catalog/#apps-workflow-automation) |
| [Security, Privacy & Legal](./catalog/#security-privacy-legal) | [Product, Design & UX](./catalog/#product-design-ux) | [Finance, Trading & Markets](./catalog/#finance-trading-markets) |
| [Specialized Domains & Utilities](./catalog/#general-utilities) | [Chinese Platform Workflows](./catalog/#chinese-platform-workflows) | |

### Starter kits

| Kit | Agents | Intended use |
|---|---|---|
| [Solo Founder](./starter-kits/solo-founder/) | CEO, PE, CCO | Planning, engineering, and reviewed content drafts |
| [Content Creator](./starter-kits/content-creator/) | CCO, CDO, CMO | Research, content drafts, and measurement plans |
| [Quant Trader](./starter-kits/quant-trader/) | CQO, CDO, CFO | Research, backtesting, and risk review—not live trading |
| `full-team` | All manifest agents | Broad evaluation; start smaller when possible |

## Choose a distribution

| Surface | Repository support | Install path | Evidence boundary |
|---|---|---|---|
| Generic/local workspace | Supported by `install.sh` | Preview, inspect, then apply | Installer behavior is covered by integration tests |
| Codex | Separate curated native package | See [`.codex/INDEX.md`](./.codex/INDEX.md) | Native package and generic kits are separate distributions |
| Claude Code | Plugin manifest present | Review [`.claude-plugin/`](./.claude-plugin/) | Confirm support in the installed client version |
| Cursor, Gemini, Kimi | Metadata or manifests present | Review the corresponding files | Presence does not establish feature parity |

## Evidence and verification

Repository contracts calculate catalog facts from tracked files and the canonical manifest:

```bash
npm test
npm run validate
npm run validate -- --warnings-as-errors
```

A web page displays `Verified` only when its [verification receipt](./docs/data/verification-receipt.json) matches the current `main` commit and every recorded check passes.

When making an outcome claim, link the reproducible input, fixture, revision, result, limitations, and rollback path. Tests are evidence of repository behavior, not a guarantee of business performance.

## Repository architecture

```text
AGI-Super-Team/
├── config/          # Canonical team manifest, schema, and removed-link provenance
├── agents/          # Role, identity, workflow, and tool guidance
├── skills/          # Tracked physical skills; symlinks are forbidden
├── catalog/         # Generated task taxonomy and machine-readable skill index
├── starter-kits/    # Focused team selections
├── install.sh       # Preview-first generic workspace installer
├── scripts/         # Repository model, validator, and Pages data builder
├── tests/           # Repository, installer, site-data, and SEO contracts
├── docs/            # Evidence First Pages site and editorial guides
├── growth/          # Human-reviewed launch and measurement playbooks
└── assets/          # README, social preview, logo, and demo assets
```

The control flow is:

```text
config/team-manifest.json
  → scripts/repository_model.py
  → install.sh + validator + tests

config/external-skill-sources.json
  → portable provenance for removed machine-local links
```

README text is not an inventory source. See [the manifest](./config/team-manifest.json), [repository model](./scripts/repository_model.py), and [contribution policy](./CONTRIBUTING.md) for the contracts.

## Team topology

```text
Founder / operator
└── CEO — coordination and quality gates
    ├── CTO / PE — architecture and implementation
    ├── CPO / CCO / CMO — product, content, and growth
    ├── CQO / CFO / CDO — quantitative research, finance, and data
    ├── CLO / CRO / CSO / COO — legal, research, sales, and operations
    └── Governor — independent review and escalation
```

Mentor names are creative framing. They do not imply affiliation, endorsement, or guaranteed imitation.

## Safety boundaries

- Never place credentials, private user data, browser sessions, or production configuration in a skill or issue.
- Review third-party commands and dependencies before execution.
- Keep financial workflows in research or paper-trading environments until independently validated.
- Require explicit human approval for posts, messages, transactions, deployments, and destructive operations.
- Report vulnerabilities privately through [GitHub Security Advisories](https://github.com/aAAaqwq/AGI-Super-Team/security/advisories/new).

## Project links

- [Evidence First project site](https://aaaaqwq.github.io/AGI-Super-Team/)
- [Practical guides](./docs/guides/)
- [Setup and recovery](./setup.md)
- [Contributing and provenance](./CONTRIBUTING.md)
- [Security policy](./SECURITY.md)
- [Growth playbooks](./growth/README.md)
- [License](./LICENSE)

## Star History

![Star History](https://aaaaqwq.github.io/AGI-Super-Team/assets/star-history.svg)
