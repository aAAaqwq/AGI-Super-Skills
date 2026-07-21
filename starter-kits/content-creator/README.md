# Content Creator starter kit

This kit selects CCO for drafting, CDO for research and measurement, and CMO for positioning. It does not install the separate Codex-native package or publish to external platforms.

## Safe install

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace content-creator
./install.sh --source "$PWD" --destination /path/to/review-workspace --apply content-creator
```

Run the first command as a preview. Run the second only after reviewing the proposed `workspace-cco`, `workspace-cdo`, and `workspace-cmo` paths. Existing files and skill directories are preserved.

## Evaluation prompts

- CDO: “Summarize the supplied, licensed dataset and list missing evidence. Do not scrape private or restricted sources.”
- CCO: “Draft a post from the approved evidence pack. Mark unsupported claims and do not publish.”
- CMO: “Design a one-week ethical experiment with a hypothesis, audience, metric, stop condition, and manual review gate.”

Respect platform rules, consent, attribution, and community norms. All posts and replies must be reviewed and sent manually by an authorized human.

See [the setup guide](../../setup.md) and [growth playbooks](../../growth/README.md).
