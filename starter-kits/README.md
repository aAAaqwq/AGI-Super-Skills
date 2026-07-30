# 🎯 Outcome Team Armies

Start with the smallest complete army that can own the outcome. Each Team selects existing executives and specialists through `config/team-manifest.json`.

The same contract can be adapted to Claude Code, Codex, OpenClaw, Hermes, and other supported frameworks.

The files define organization, routing, and review. They do not start a runtime or guarantee task quality.

| Team army | Best for | Core roles | Runbook |
|---|---|---|---|
| 🚀 Solo Founder | Product decisions, MVP delivery, and launch preparation | CEO, CPO, PE, Governor | [Open](./solo-founder/RUNBOOK.md) |
| ✍️ Content Creator | Evidence-led content, channel adaptation, and measurement | CEO, CRO, CCO, CMO, Governor | [Open](./content-creator/RUNBOOK.md) |
| 📊 Quant Research | Reproducible backtesting and independent risk review | CEO, CQO, CDO, CFO, Governor | [Open](./quant-trader/RUNBOOK.md) |
| 🧱 Product Delivery | Product discovery, architecture, implementation, and release handoff | CEO, CPO, CTO, PE, Governor | [Open](./product-delivery/RUNBOOK.md) |
| 🔬 Research Decision | Primary evidence, uncertainty, and consequential decisions | CEO, CRO, CDO, Governor | [Open](./research-decision/RUNBOOK.md) |
| 📣 Go To Market | Positioning, launch assets, revenue experiments, and risk gates | CEO, CPO, CMO, CCO, CSO, Governor | [Open](./go-to-market/RUNBOOK.md) |
| 🚨 Operations Response | Incident containment, recovery, evidence, and review | CEO, COO, CTO, PE, Governor | [Open](./operations-response/RUNBOOK.md) |
| 🏛️ Executive Team | Cross-functional company outcomes requiring broad optional coverage | All 14 top-level roles eligible; CEO coordinates, Governor reviews | [Open](./full-team/RUNBOOK.md) |

Preview a kit without writing files:

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace solo-founder
```

Return to the [project overview](../README.md) or read the complete [setup and recovery guide](../setup.md).
