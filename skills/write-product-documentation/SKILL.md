---
name: write-product-documentation
description: Create and maintain a fact-based product documentation system from source code, tests, UI, configuration, and release evidence. Use when writing a product description, full user manual, daily operations guide, installation guide, technical specification, acceptance document, release note, FAQ, or when reconciling conflicting and outdated product claims across versions and platforms.
---

# Write Product Documentation

Write from verified product behavior, not aspiration. Give each document one audience and one job, while preserving a shared fact base.

## Workflow

1. **Freeze scope.** Record product version, commit/tag, platform, deployment mode, audience, and date. Do not mix future features or another branch into current instructions.
2. **Build a fact matrix.** Map each claim to code, configuration, test, screenshot, runtime evidence, and known limitation. Mark facts as verified, inferred, planned, or unknown.
3. **Choose the document role.** Use a product description for value and boundaries, a full user manual for end-to-end operation, a daily guide for routine use, a technical specification for implementation, and an acceptance document for testable outcomes.
4. **Design the user journey.** Lead from prerequisites to first success, normal operation, exceptions, recovery, data handling, and support. Explain parameters in business terms.
5. **Write exact side-effect semantics.** State what preview/dry-run does for each operation. Distinguish “processed,” “request sent,” “artifact received,” “verified,” and “persisted.”
6. **Separate platforms and versions.** Put Windows/macOS differences where users encounter them. Never let an old platform prerequisite leak into a new implementation.
7. **Use honest product language.** Explain value first, but avoid unsupported detection, compliance, ROI, security, or availability guarantees. State human decision points and external dependencies.
8. **Create acceptance traceability.** Turn every important promise into a precondition, action, expected result, evidence, and failure criterion.
9. **Validate the deliverable.** Check links, headings, terminology, screenshots, version strings, commands, privacy, accessibility, rendering, and consistency against the fact matrix.
10. **Retire stale documents.** Archive superseded evidence with a replacement link; do not leave multiple files claiming to be the current source of truth.

## Writing rules

- Use the reader's language before internal implementation names.
- Define one term once and reuse it consistently.
- Give copyable commands only after verifying them on the scoped version.
- Keep screenshots synthetic or redacted and bind each screenshot to the documented version/platform.
- Distinguish product boundary, known limitation, expected degradation, and defect.
- Do not hide real side effects under “preview” wording.
- Keep legal/privacy/security claims aligned with the current architecture and policy review.

## References

- Read [document-system.md](references/document-system.md) to select document types, structures, and validation gates.
- Read [project-evidence.md](references/project-evidence.md) for examples and contradictions found in this repository's documentation set.
