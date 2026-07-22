# Ten-round quality iteration record

This record documents one repository improvement cycle. Scores are internal review aids, not independent benchmarks or product claims.

## Rubric

- **Taste:** hierarchy, density, copy discipline, purposeful visual language, and mobile readability.
- **First use:** a new visitor can identify Skills, Agents, Starter Kits, distributions, commands, and evidence boundaries.
- **Architecture:** source authority, Module depth, Interface coherence, Seam quality, Locality, and test leverage.
- **Skill quality:** valid metadata, trigger precision, progressive disclosure, portable resources, execution evidence, and explicit risk boundaries.

Each dimension uses a 0 to 10 scale. Swarm reviewers challenged the baseline and rounds 9 and 10. Scores moved only when a file, test, generated artifact, or rendered-browser check supplied evidence.

## Iterations

| Round | Change | Taste | First use | Architecture | Skill quality | Evidence |
|---:|---|---:|---:|---:|---:|---|
| 1 | Baseline audit | 6.8 | 6.3 | 5.6 | 4.8 | README, Pages, navigation, architecture, and all canonical Skill entrypoints audited |
| 2 | README density | 7.6 | 7.1 | 5.6 | 4.8 | Long source dump replaced by three intent-based references |
| 3 | Copy discipline | 8.1 | 7.4 | 5.6 | 4.8 | Public Hero copy cleared of dash and separator violations; Emoji kept for navigation |
| 4 | Truthful Hero and CTA | 8.5 | 8.3 | 5.7 | 4.8 | Generic preview and Codex package routes separated; unverified outcome claim removed |
| 5 | Responsive browser QA | 8.7 | 8.6 | 5.7 | 4.8 | 1536×1024 and 390×844 checks; no horizontal overflow; menu, theme, and 44px targets passed |
| 6 | Architecture map | 8.7 | 8.6 | 6.3 | 4.9 | Authored inputs, generated outputs, distributions, evidence flow, and change ownership documented |
| 7 | Canonical navigation | 8.7 | 8.9 | 6.5 | 5.0 | Starter Kits, Cookbooks, Plugins, bilingual, and compatibility routes added; legacy docs became routers |
| 8 | Skill evidence seam | 8.7 | 9.0 | 6.6 | 7.0 | YAML, link, resource, portability, disclosure, and script evidence report plus debt ratchet added |
| 9 | Representative Skill repair | 8.7 | 9.0 | 6.9 | 8.0 | Source index, content toolkit, Clanker, and CT Monitor metadata and risk boundaries improved |
| 10 | Fail-closed verification | 8.7 | 9.5 | 6.9 | 8.7 | Canonical tracked inventory reused; whole Skill trees scanned; CI dependencies and regression tests completed |

## Round 10 limits

- Architecture remains capped by missing current-client harness receipts and public task-behavior fixtures.
- Structural Skill evidence is not semantic verification. The checked baseline records existing debt and prevents regression; it does not certify all catalog entries.
- `ct-monitor` remains above the preferred 500-line entrypoint limit and should be split through a separate progressive-disclosure refactor.
- Star data is a community signal. It is never used as proof of safety or quality.

## Reproduce the final gate

```bash
python3 -m pip install --requirement requirements-dev.txt
npm test
npm run validate -- --warnings-as-errors
npm run check:skills
npm run check:skill-quality
bash -n install.sh
git diff --check
```
