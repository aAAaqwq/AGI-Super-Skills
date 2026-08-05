# 🚀 Solo Founder starter kit

Turn one bounded product brief into a decision memo, test-first delivery plan, optional launch evidence pack, and Governor review.

- **Core:** CEO coordinator, CPO, PE, Governor reviewer.
- **Full:** adds CCO and CMO when communication or distribution is in scope.
- **Workflow:** [read the canonical runbook](./RUNBOOK.md).

Preview the portable coordinated layout:

```bash
./install.sh --source "$PWD" --destination /path/to/agi-team \
  --layout coordinated --skill-tier core --team-tier core --kit solo-founder
```

Add `--apply` only after reviewing the plan. The command materializes role files; use the Codex [`$c-suite-team`](../../plugins/agi-super-team-codex/skills/c-suite-team/) adapter for native delegation. Publishing, deployment, merge, credentials, purchases, and destructive actions remain human-controlled.
