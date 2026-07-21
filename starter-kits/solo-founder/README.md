# Solo Founder starter kit

This kit selects three generic-workspace agents: CEO for planning, PE for engineering, and CCO for content drafts. It does not install the separate Codex-native package.

## Safe install

From a reviewed checkout, preview first:

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace solo-founder
```

Apply only after checking the planned paths and agents:

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace --apply solo-founder
```

The expected directories are `workspace-ceo`, `workspace-pe`, and `workspace-cco`. Existing files and skill directories are preserved.

## Evaluation prompts

- CEO: “Draft a product decision memo with assumptions, alternatives, evidence gaps, and a human approval gate.”
- PE: “Propose a test-first implementation plan. Do not deploy or change production systems.”
- CCO: “Draft three launch-post variants with factual claim placeholders and a manual publishing checklist.”

Review every output. Publishing, deployments, account access, and other external actions require explicit human authorization.

See [the setup guide](../../setup.md) for verification, updates, and recovery.
