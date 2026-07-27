# Software copyright registration workflow

## 1. Freeze registration facts

Record software name, version, short name, platform, developer, owner, development method, completion date, publication status/date/place, language, source size, runtime environment, and selected Git tag/commit. Confirm every field against evidence and current official form requirements.

## 2. Export source reproducibly

- Read source from the frozen commit, not the current working tree.
- Include owned core source in a deterministic file order.
- Exclude dependencies, generated bundles, binaries, vendored code, secrets, personal data, test fixtures containing private data, and irrelevant artifacts.
- Record original line counts, filters, ordering, selected ranges, and source commit.
- Apply the current jurisdiction's deposit rules only after checking official guidance; do not reuse old page/line assumptions blindly.

## 3. Prepare software documentation

Choose a user manual or design specification that is true for the registered baseline. Keep name, version, platform, modules, UI, and screenshots consistent with the source deposit and application form. Do not describe later branch features.

## 4. Handle screenshots and private inputs

- Use synthetic or fully redacted data.
- Remove real contacts, resumes, chats, API keys, account identifiers, and browser profile details.
- Keep identity documents, signatures, addresses, and private application fields in an ignored private directory.
- Make generated public documents fail closed when required private inputs are absent in final mode.

## 5. Generate and validate

Use deterministic generators where possible. Produce:

- source file inventory and source deposit;
- application-field worksheet;
- user/design document;
- ownership statement when actually required;
- text, page, line, version, privacy, render, and hash reports.

Render every PDF page to images and inspect first, boundary, and final pages plus pages containing large screenshots or tables. Check headers, page numbers, clipping, fonts, blank pages, placeholders, and consistency.

## 6. Final package

Record final filenames, sizes, SHA-256, source baseline, generator command, generation date, and review status. Keep portal-generated official forms separate from local drafting worksheets. Do not mark complete until identity, signatures, publication facts, ownership, and current portal requirements are confirmed.
