# Debug swarms

Use parallel debugging only after reproducing the symptom and identifying multiple plausible, independently testable causes.

Assign one hypothesis per `hypothesis-debugger`. Require:

- A precise causal statement.
- Expected evidence if true.
- Falsifying evidence.
- The cheapest read-only discriminating checks.
- File-and-line or command-output evidence.
- A final status: confirmed, plausible, falsified, or inconclusive.
- Calibrated confidence and remaining uncertainty.

Generate hypotheses across logic, data, state/concurrency, integration, resources, and environment. Avoid giving all workers the favored hypothesis, which recreates confirmation bias.

The parent arbitrates results, checks contradictory evidence, identifies compound causes when warranted, and sends only the winning root cause to a write-capable `debugger` for a minimal tested fix.

Adapted from `agent-teams/skills/parallel-debugging` in `wshobson/agents` commit `767d969a73ce6608d10ac713e52be9ac7f061ab9` (MIT).
