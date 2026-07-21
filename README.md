<p align="center">
  <img src="assets/banner.png" alt="AGI Super Team — Evidence-backed AI teams for real outcomes" width="100%">
</p>

<h1 align="center">AGI Super Team</h1>

<p align="center"><strong>Evidence-backed AI teams for real outcomes</strong></p>

<p align="center">
  <a href="./README_CN.md">中文</a> ·
  <a href="#safe-quick-start">Quick start</a> ·
  <a href="./setup.md">Setup guide</a> ·
  <a href="./CONTRIBUTING.md">Contribute</a>
</p>

## What this repository is

AGI Super Team is a collection of agent personas, reusable skills, starter-kit manifests, and a curated Codex-native package. It helps people assemble reviewable AI workflows rather than promising autonomous business results.

Outputs still need human review. Trading, legal, security, medical, publishing, and deployment tasks require domain-specific validation and appropriate authorization.

## Choose a distribution

| Surface | Repository support | Install path | Notes |
|---|---|---|---|
| Generic/local workspace | Supported by `install.sh` | Preview, inspect, then apply | Copies selected personas and available skills without overwriting existing files |
| Codex | Separate curated native package | See [`.codex/INDEX.md`](./.codex/INDEX.md) | Has its own manifest, selected skills, and opt-in agent sync |
| Claude Code | Repository plugin manifest present | Review [`.claude-plugin/`](./.claude-plugin/) | Confirm your installed client supports the manifest before use |
| Cursor, Gemini, Kimi | Metadata/manifests present | Review the corresponding manifest | Compatibility varies by client version; this repository does not claim feature parity |

The generic starter kits and Codex package are separate products. Installing one does not install or synchronize the other.

## Safe quick start

Clone a trusted revision and preview the local installer. Preview is read-only and is the default.

```bash
git clone --depth 1 --branch main https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team
./install.sh --source "$PWD" --destination /path/to/review-workspace solo-founder
```

Review the proposed agents, source, destination, and relevant files. Apply only after the preview matches your intent:

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace --apply solo-founder
```

The installer preserves existing persona files and skill directories. See [setup.md](./setup.md) for prerequisites, verification, updates, and recovery.

Avoid piping a remote script directly into a shell when you can inspect a pinned checkout first.

### Preview → apply → verify

<p align="center">
  <img src="assets/demo-install.gif" alt="Terminal demo showing a read-only preview, explicit apply, and repository checks passing" width="760">
</p>

The animation uses sanitized project-relative paths. Read the [static transcript](./assets/demo-install.txt) or run the same commands in a clean checkout.

## Packages and manifests

- [Codex package index](./.codex/INDEX.md): curated Codex skills, specialist roles, sync behavior, provenance, and update policy.
- [Codex marketplace manifest](./.agents/plugins/marketplace.json): points to the separate `plugins/agi-super-team-codex` package.
- [Starter kits](./starter-kits/): small selections for a solo founder, content team, or quantitative research workflow.
- [Agents](./agents/): persona and operating files for the generic workspace installer.
- [Skills](./skills/): the cross-harness skill library. Its contents change; use the repository validator instead of a hard-coded count.

## Starter kits

| Kit | Agents | Intended use |
|---|---|---|
| [Solo Founder](./starter-kits/solo-founder/) | CEO, PE, CCO | Planning, engineering, and reviewed content drafts |
| [Content Creator](./starter-kits/content-creator/) | CCO, CDO, CMO | Research, content drafts, and measurement plans |
| [Quant Trader](./starter-kits/quant-trader/) | CQO, CDO, CFO | Research, backtesting, and risk review—not live trading |
| `full-team` | All repository agents | Broad evaluation; start smaller when possible |

Examples describe tasks the agents can assist with, not validated performance claims. External publishing, financial transactions, and production changes remain manual and human-authorized.

## Evidence and verification

Repository checks are the source of truth for catalog integrity:

```bash
npm test
npm run validate
```

Do not publish exact catalog counts until the validator is green for the revision being described. When making a claim, link to reproducible inputs, record the revision, and distinguish tests from real-world validation.

## Architecture

```text
Founder / operator
└── CEO — coordination and quality gates
    ├── CTO / PE — architecture and implementation
    ├── CPO / CCO / CMO — product, content, and growth
    ├── CQO / CFO / CDO — quantitative research, finance, and data
    ├── CLO / CRO / CSO / COO — legal, research, sales, and operations
    └── Governor — independent review and escalation
```

Each agent directory may contain persona, identity, workflow, and tool guidance. Treat mentor names as creative framing, not affiliation, endorsement, or an imitation guarantee.

## Safety boundaries

- Never place credentials, private user data, browser sessions, or production configuration in a skill or issue.
- Review third-party commands and dependencies before execution.
- Run financial workflows in research or paper-trading environments until independently validated; no bundled strategy is guaranteed profitable or production-ready.
- Require explicit human approval for posts, messages, transactions, deployments, and destructive operations.
- Report vulnerabilities privately through [GitHub Security Advisories](https://github.com/aAAaqwq/AGI-Super-Team/security/advisories/new), not a public issue.

## Project links

- [Setup and recovery](./setup.md)
- [Contributing and provenance](./CONTRIBUTING.md)
- [Security policy](./SECURITY.md)
- [Growth playbooks](./growth/README.md)
- [License](./LICENSE)

## Star History

![Star History](https://aaaaqwq.github.io/AGI-Super-Team/assets/star-history.svg)
