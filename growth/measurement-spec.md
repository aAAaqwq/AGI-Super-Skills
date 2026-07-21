# Measurement specification

Measure whether people understand and reproduce a useful outcome—not raw impressions alone.

## Primary outcomes

| Metric | Definition | Evidence |
|---|---|---|
| Qualified repository visit | Visit from a relevant post with documented campaign tag | Aggregate analytics if lawfully available |
| Preview completion | User reports or test session reaches installer preview without unintended writes | Sanitized test record |
| MVTA reproduction | Independent user completes isolated apply and verification at a recorded revision | Reproduction checklist |
| Useful feedback | Specific question, correction, bug, or use-case evidence | Sanitized feedback entry |
| Trust correction | Misleading or unclear claim identified and corrected | Claim-ledger history |

## Guardrails

Track post removals, moderator warnings, unsubscribe/block requests, security reports, unexpected writes, misleading-claim corrections, and harassment. Any severe event triggers the stop procedure.

## Event fields

Use `occurred_at`, `channel`, `campaign_id`, `artifact_revision`, `event_type`, `aggregate_count`, `evidence_location`, and `notes`. Do not store handles, email addresses, IP addresses, message contents, or cross-site identity profiles without a documented lawful need and consent.

## Interpretation

Compare small experiments with a recorded baseline. Do not infer causality from correlation, combine incomparable channels, or optimize for clicks that do not produce qualified learning. Report denominators, observation windows, missing data, and changes to definitions.

Retain only the minimum aggregate data needed for the 90-day decision, then delete or anonymize it according to the owner’s policy.
