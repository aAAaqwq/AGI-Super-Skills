# Patent drafting workflow for software mechanisms

## 1. Invention inventory

For each candidate mechanism, record:

- technical problem in a concrete computing environment;
- prior failure mode and why ordinary approaches are insufficient;
- ordered technical steps and state transitions;
- inputs, outputs, persistent state, and failure behavior;
- measurable technical effect;
- implementation files, tests, logs, and first-known date;
- likely neighboring mechanisms and overlap risk.

Split candidates when each has an independent technical center and can be implemented without the other. Combine only when the interaction itself is the inventive mechanism and the specification supports the combination.

## 2. Search before certainty

Search current patent and non-patent literature by mechanism, not product wording. Build a claim-element comparison table:

| Proposed element | Closest reference | Same/different | Evidence for distinction | Drafting consequence |
|---|---|---|---|---|

Record database, query, date, language, publication number, family, and relevance. A preliminary search supports drafting; it does not establish grantability.

## 3. Drafting package

Create, as jurisdiction requires:

- technical disclosure;
- description/specification;
- independent and dependent claims;
- abstract;
- drawings and drawing descriptions;
- request-form fact sheet;
- code/claim/test mapping;
- prior-art and overlap assessment;
- filing checklist.

Draft independent claims around the minimum complete technical loop. Use dependent claims for variants, thresholds, fallback paths, data structures, security controls, and implementation details. Ensure every claim term has support in the description and drawings.

## 4. Drawings

Use consistent names and reference numerals. Prefer system architecture, method flow, state machine, sequence/evidence chain, and data relationship figures. Verify every figure is cited, every cited figure exists, and labels match the text.

## 5. Evidence and regression

Map each key claim element to source and test evidence. Freeze relevant regression output at the proposed filing commit. Include negative tests that show the mechanism blocks unsafe or conflicting states; they often explain the technical effect more clearly than happy-path examples.

## 6. Final gates

- Claims, specification, abstract, and drawings use the same terminology.
- Current implementation supports the claimed scope or the description clearly enables supported variants.
- Overlapping applications have deliberate boundaries.
- Applicant, inventors, ownership, public disclosure, priority, assignment, and employment status are confirmed.
- Current official format, electronic filing, fee, signature, and representation requirements are checked.
- A qualified reviewer completes novelty, inventive-step/non-obviousness, clarity, support, enablement, unity, and filing-strategy review.
