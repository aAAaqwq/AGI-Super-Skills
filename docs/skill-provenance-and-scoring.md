# Skill provenance and Curation evidence score

This repository distinguishes inventory, provenance, curation, and runtime evidence. They answer different questions and must not be collapsed into one badge.

## Evidence layers

| Layer | Authority | Meaning |
|---|---|---|
| Inventory | tracked physical `skills/*/SKILL.md` | The Skill exists in this revision. |
| Provenance | `config/skill-provenance.json` | Reviewed evidence for where the Skill came from. |
| Curation | `config/skill-curation.json` | A digest-matched editorial review using the score model below. |
| Runtime | commit-matched fixture or beta receipt | The named workflow ran under the stated conditions. |

Generated catalog files are discovery outputs, never authorities. The removed-link ledger in `config/external-skill-sources.json` contains tombstones and must not be used as active provenance.

## Origin labels

- **Project original:** authorship, creation commit, local digest, and license evidence were reviewed.
- **Adapted:** a pinned upstream source and license were reviewed, and local adaptations are documented.
- **Collected:** a pinned upstream source and license were reviewed, with no claim of original authorship.
- **Unknown:** evidence is incomplete. `community`, `ECC`, an author field, a homepage, or Git committer identity alone is only a hint.

Unreviewed Skills default to `Unknown`. The system never guesses `Collected` merely because a Skill looks external.

## Curation evidence score

The **Curation evidence score** is a 0–100 editorial evidence score:

| Dimension | Maximum |
|---|---:|
| Instruction design and trigger precision | 15 |
| Resource integrity and maintainability | 15 |
| Safety, reversibility, and limitation disclosure | 20 |
| Provenance and license completeness | 20 |
| Outcome-oriented examples, checks, fixtures, and receipts | 30 |

Tiers are `Exemplary` (95–100), `Recommended` (85–94), `Selected` (75–84), `Candidate` (60–74), and `Hold` (below 60).

Fail-closed rules:

- Structurally invalid Skills and Skills awaiting execution review cannot be Selected.
- Selected Skills require reviewed, non-Unknown provenance and a score of at least 75.
- `runtime_evidence: pending` caps the score at 84.
- Changing any tracked file in a reviewed Skill changes its tree digest. The review becomes `Stale` and the public number is hidden until re-review.
- The score never means `Verified`, production-ready, safe for every environment, or compatible with every harness.

## Runtime evidence

Runtime status remains a separate field: `pending`, `prompt-tested`, `fixture-one-harness`, `fixture-two-harness`, or `external-beta`. Only the repository's commit-matched receipt policy can authorize a runtime `Verified` claim.

## Review workflow

1. Inspect the complete Skill directory, permissions, dependencies, risk, source, and license.
2. Resolve the origin conservatively and pin external sources to a commit.
3. Record the tracked-tree digest.
4. Score each dimension with evidence paths and explicit limitations.
5. Run `npm run build:skills` and `npm run build:agent-indexes`.
6. Run repository checks. A later Skill change intentionally invalidates the published score.
