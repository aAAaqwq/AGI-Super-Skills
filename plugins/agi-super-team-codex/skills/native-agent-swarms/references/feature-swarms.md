# Feature swarms

Parallelize implementation only after requirements, interfaces, and verification criteria are stable enough for independent work.

Choose a split:

- Vertical slices when each user-visible slice can be tested independently.
- Horizontal layers when ownership naturally follows frontend, backend, data, or tests.
- Hybrid when shared infrastructure needs one dedicated owner.

Enforce one owner per file. Designate one owner for shared contracts, generated indexes, lockfiles, migrations, and barrel files. Other workers may request changes but must not edit those files.

Freeze interface contracts before spawning when possible. Include inputs, outputs, errors, versioning, and test doubles in each dispatch contract. If a contract changes, notify only affected workers and update acceptance criteria.

Integrate in dependency order. After all streams finish, the parent reviews the combined diff, runs contract and integration tests, then runs the broader relevant suite. Do not ask workers to create branches, commits, pushes, deployments, or pull requests unless the user explicitly authorized that exact external action.

Adapted from `agent-teams/skills/parallel-feature-development`, `task-coordination-strategies`, `team-communication-protocols`, and `team-composition-patterns` in `wshobson/agents` commit `767d969a73ce6608d10ac713e52be9ac7f061ab9` (MIT).
