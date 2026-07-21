# Review swarms

Assign non-overlapping dimensions, normally 2-4 of correctness, security, architecture, performance, testing, accessibility, database, or language-specific behavior. Give every reviewer the same target diff and requirements but a distinct lens.

Each finding must include severity, exact location, evidence, user or system impact, and a concrete remediation. Treat style-only preferences as low priority or omit them.

During synthesis:

1. Merge the same issue at the same location.
2. Keep different issues at the same location separate.
3. Cross-reference the same issue across different locations.
4. Resolve conflicting severity from exploitability and impact evidence, not by voting.
5. Verify critical and high findings directly before reporting them.

Use severity consistently: critical for likely catastrophic compromise or data loss; high for significant likely failure; medium for bounded impact or a viable workaround; low for minor risk.

Adapted from `agent-teams/skills/multi-reviewer-patterns` in `wshobson/agents` commit `767d969a73ce6608d10ac713e52be9ac7f061ab9` (MIT).
