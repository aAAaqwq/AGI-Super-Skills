# Project evidence: software IP materials

## Evidence baseline

- Main baseline reviewed: `origin/main` at `401ad9c`, including patent and software-copyright work merged before that commit.

## Patent sources

- `docs/patents/README.md`: portfolio inventory, independent technical centers, and status language.
- `docs/patents/组合管理/`: shared applicant facts, boundaries, filing route, and unified checklists.
- Per-application folders: technical disclosure, claims, specification, abstract, drawings, request facts, and implementation mappings.
- `docs/patents/递交前核对清单.md`: search, ownership, procedural, evidence, and release gates.
- `docs/patents/B-D回归修复与安全测试证据.md`: code/test evidence and corrected regression claims.

## Software-copyright sources

- `docs/软件著作权申请/README.md`: frozen baseline, private-input separation, generators, outputs, and current status.
- `00-申报总计划.md`: fact freeze, evidence inventory, source deposit, documentation, QA, and filing stages.
- `tools/build_copyright_package.py` and `tools/build_design_document.py`: reproducible generation from a frozen Git baseline.
- `质量核验/`: page, line, consistency, privacy, rendering, and checksum reports.
- `截图/`: redacted, version-scoped UI evidence.

## Reusable lessons

1. Freeze the exact code baseline before drafting; later branch work must remain outside the registered scope.
2. Keep personal filing data in one ignored private input rather than duplicating it into tracked drafts.
3. Patent files need a code/claim/test map, not just polished prose.
4. Corrected test fixtures and negative tests are part of the evidence trail; preserve the earlier report and document the correction.
5. Draft/final generation modes should differ: draft may show placeholders, while final must refuse incomplete inputs.
6. Text extraction alone cannot validate PDFs. Render every page and preserve hashes.
7. “Complete working draft” and “ready to file” are distinct states; search, ownership, current forms, and qualified review remain independent gates.
