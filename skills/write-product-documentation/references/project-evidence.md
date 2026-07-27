# Project evidence: product documentation

## Evidence baseline

- Main baseline reviewed: `origin/main` at `401ad9c`.
- Windows implementation comparison: `codex/win-native-uia-1.1.7` at `526abba`.

## Primary sources

- `docs/产品说明书.md`: persona, pain, value, differentiators, boundaries, and product positioning.
- `docs/产品使用手册.md`: installation, interface, workflows, side effects, configuration, and troubleshooting.
- `docs/日常使用手册.md`: recurring operating rhythm and human checkpoints.
- `docs/验收文档.md`: feature and non-functional acceptance matrix.
- `docs/README.md`: current versus historical document routing.
- `docs/process/`: code-aligned business process specifications.
- `CHANGELOG.md`: version-scoped behavior changes.

## Reusable lessons

1. One document cannot serve sales, onboarding, daily operation, technical design, and acceptance equally well. Assign each a distinct role.
2. Parameter semantics must be business-visible. In this project, the same `limit` shape means successful actions in one process and top-N reviewed contacts in another.
3. “Preview” is not universally side-effect free. Each operation needs its own explicit side-effect table.
4. Product claims drift when platform branches diverge. The main manual can still mention an older Windows driver after the Windows branch has removed it; branch and version scope must be stated.
5. Result language matters. “Clicked,” “requested,” “received,” “verified,” and “stored” are different states and must not be collapsed.
6. The strongest acceptance document maps promises to observable results and failure conditions, not just scripts or test totals.
7. Archiving old investigation notes with replacement links reduces contradictory sources while preserving traceability.
