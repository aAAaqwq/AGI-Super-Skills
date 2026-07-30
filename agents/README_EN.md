<p align="right"><a href="./README.md">中文</a></p>

# 👥 Agents — C-suite digital executives

> One-person-company template: 14 top-level C-suite AI roles with optional specialist pyramids.

## Organization

```text
Founder / Chair
    ↓ direction and approval
CEO (ceo)
    ├── CTO → canonical PE + 22 engineering specialists
    ├── CPO → 3 product-design specialists
    ├── CCO → 19 content and organic-growth specialists
    ├── CFO → 8 finance specialists
    ├── CDO → 5 data specialists
    ├── CQO → 4 quantitative-research specialists
    ├── CMO → 7 marketing specialists
    ├── CRO → 6 evidence and research specialists
    ├── CSO → 8 sales and customer-success specialists
    ├── COO → 4 operations specialists
    ├── CLO → 6 legal and compliance specialists
    └── Governor → independent assurance
```

The hierarchy contains eleven bounded managers and 92 direct specialists. CEO remains the root coordinator; Governor remains an independent review leaf; PE remains CTO's canonical production-delivery leaf rather than a second manager.

```text
agents/
├── cto/subagents/<role>/AGENTS.md   # 22 engineering specialists; PE reuses agents/pe
├── cpo/subagents/<role>/AGENTS.md   # 3 product-design specialists
├── cco/subagents/<role>/AGENTS.md   # 19 content and growth specialists
├── cfo/subagents/<role>/AGENTS.md   # 8 finance specialists
├── cdo/subagents/<role>/AGENTS.md   # 5 data specialists
├── cqo/subagents/<role>/AGENTS.md   # 4 quantitative specialists
├── cmo/subagents/<role>/AGENTS.md   # 7 marketing specialists
├── cro/subagents/<role>/AGENTS.md   # 6 research specialists
├── cso/subagents/<role>/AGENTS.md   # 8 sales specialists
├── coo/subagents/<role>/AGENTS.md   # 4 operations specialists
└── clo/subagents/<role>/AGENTS.md   # 6 legal and compliance specialists
```

Vendored specialist `AGENTS.md` files are byte-for-byte copies from a pinned upstream commit. [`agent-hierarchy.json`](../config/agent-hierarchy.json) owns parent-child edges, [`*-specialists.json`](../config/) owns routing and safety, and [`agent-sources.lock.json`](../config/agent-sources.lock.json) owns source URLs and hashes. Do not edit vendored role text directly.

## Install specialist groups

The default installs only the 14 top-level roles. Select one manager group or all 92 specialists:

```bash
# Preview CFO specialists; append --install after review
npx -y github:aAAaqwq/AGI-Super-Team --tool codex --with-subagents cfo

# Install every executive specialist
npx -y github:aAAaqwq/AGI-Super-Team --tool codex --all-subagents --install
```

Manager IDs: `cto`, `cpo`, `cco`, `cfo`, `cdo`, `cqo`, `cmo`, `cro`, `cso`, `coo`, and `clo`. Nested Codex delegation requires `max_depth = 2`; otherwise the CEO must dispatch the same specialist directly and disclose the flat fallback.

## Top-level role index

| Agent | Responsibility | Mentor archetype |
|---|---|---|
| [CEO](ceo/) | Strategy, prioritization, and orchestration | Elon Musk |
| [CTO](cto/) | Technology strategy and architecture | Jensen Huang |
| [PE](pe/) | Production engineering and delivery | Linus, antirez, DHH |
| [CQO](cqo/) | Quantitative research and model risk | Jim Simons |
| [CCO](cco/) | Editorial systems and content operations | MrBeast, MediaStorm |
| [CDO](cdo/) | Data contracts, quality, and governance | Nate Silver, DJ Patil |
| [CFO](cfo/) | Planning, economics, and capital constraints | Warren Buffett |
| [CMO](cmo/) | Positioning, acquisition, and measurement | David Ogilvy, Seth Godin |
| [CPO](cpo/) | Product discovery and experience | Steve Jobs, Marty Cagan |
| [CLO](clo/) | Legal issue spotting and compliance | Alan Dershowitz |
| [CRO](cro/) | Research design and evidence synthesis | Richard Feynman, Karpathy |
| [CSO](cso/) | Sales systems and customer success | Michael Dell, Aaron Ross |
| [COO](coo/) | Execution systems and operational reliability | Andy Grove, Jeff Bezos |
| [Governor](governor/) | Independent evidence and quality gate | Zhuge Liang, Wang Yangming |

## Role files and Skills

Each top-level Agent contains its role definition, identity, operating principles, memory contract, workflow, and tool index. `TOOLS.md` points to the shared [`skills/`](../skills/) library; Skills are not duplicated inside Agent directories.

```text
agents/cco/TOOLS.md ──→ skills/<skill>/SKILL.md
agents/cdo/TOOLS.md ──→ skills/<skill>/SKILL.md
agents/pe/TOOLS.md  ──→ skills/<skill>/SKILL.md
```

See the [Skills guide](../skills/README.md), [team charter](../CHARTER.md), [collaboration contract](../COLLABORATION.md), and [startup guide](../STARTUP.md) for the surrounding system.
