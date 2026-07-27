---
name: prepare-software-ip-filings
description: Prepare evidence-backed software intellectual-property materials from a frozen code baseline, including invention disclosures, patent claim packages, drawings, code-to-claim maps, software copyright source-code deposits, user or design documents, filing checklists, and reproducible quality reports. Use when inventorying patentable software mechanisms, drafting or reviewing patent materials, preparing software copyright registration, or reconciling filing documents with code, tests, releases, authorship, and publication history.
---

# Prepare Software IP Filings

Build a traceable evidence package before writing legal conclusions. Treat all filing rules, forms, fees, and portal requirements as jurisdiction- and date-sensitive; verify them against current official sources and qualified counsel.

## Workflow

1. **Freeze the baseline.** Select an immutable tag or commit, product version, platform, completion date, publication history, authorship, ownership, and excluded later work. Preserve the commit hash and clean export method.
2. **Separate public and private facts.** Keep identity numbers, addresses, signatures, credentials, customer data, and unredacted screenshots outside version control. Use one private input sheet rather than copying sensitive fields across drafts.
3. **Inventory protectable material.** Map technical problems, mechanisms, state transitions, data structures, security controls, tests, UI flows, and release evidence. Separate technical mechanisms from business goals or marketing language.
4. **Choose the filing track.** Use the patent workflow for technical solutions and claims; use the software-copyright workflow for authorship and deposited expression. Do not merge their standards or imply one grants the other.
5. **Build evidence maps.** Link every important statement to frozen source files, tests, diagrams, runtime logs, commits, and dates. Mark inferred, planned, third-party, and unsupported material.
6. **Draft consistently.** Keep product name, version, applicant/author, platform, dates, terminology, figure numbers, modules, and feature scope consistent across every document.
7. **Validate mechanically and visually.** Check source continuity, page/line counts, generated hashes, text consistency, secrets, privacy, figure references, PDF rendering, and absence of placeholders.
8. **Run independent review.** Obtain current prior-art/legal review for patents and current portal/form review for copyright. Do not label a package “ready to file” while required evidence, identity, ownership, search, or signatures remain open.
9. **Package reproducibly.** Record source baseline, generator version, inputs, output hashes, quality reports, final filenames, and which files remain private.

## Guardrails

- Do not invent dates, authorship, publication, ownership, source volume, test results, or official requirements.
- Do not treat an implementation detail as novel merely because it is complex.
- Do not claim patentability or grant probability without a current search and professional review.
- Do not include third-party or generated dependencies in source deposits unless the applicable rules and rights support it.
- Do not commit official identity documents, signatures, private forms, or candidate/customer data.
- Do not regenerate filing materials from a dirty working tree when a frozen baseline is required.
- Preserve historical evidence; correct conclusions in a new report rather than rewriting old timestamps.

## References

- Read [patent-workflow.md](references/patent-workflow.md) for invention mining, claims, drawings, search, and filing gates.
- Read [copyright-workflow.md](references/copyright-workflow.md) for frozen source deposits, manuals, screenshots, generation, and QA.
- Read [project-evidence.md](references/project-evidence.md) for the reusable evidence system extracted from this repository.
