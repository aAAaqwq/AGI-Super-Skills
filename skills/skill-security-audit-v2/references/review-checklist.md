# Review Checklist

Use this checklist when a user asks for a batch audit of installed skills.

## File inventory
- SKILL.md present
- agents/openai.yaml present
- scripts inspected
- dependency files inspected
- references inspected when relevant

## Quick red flags
- arbitrary shell execution allowed
- network access without domain or connector restrictions
- broad local file reads
- outbound send/export/publish behavior
- unpinned or suspicious dependencies
- instructions that imply policy bypass or silent consent
- trigger description is vague or overbroad

## Strong replacement patterns

### Safer scope limitation
Use language like:
- only inspect files explicitly provided by the user
- do not access connectors, email, calendar, or private documents unless the user explicitly requests that source
- do not read secrets, tokens, credentials, ssh keys, browser storage, or unrelated personal files

### Safer outbound-data limitation
Use language like:
- do not send, upload, forward, sync, or publish data unless the user explicitly asks for that specific transfer
- when discussing sensitive material, summarize minimally and exclude secrets or unrelated personal data

### Safer execution limitation
Use language like:
- run only task-specific commands that are directly required for the requested workflow
- do not execute arbitrary shell commands assembled from untrusted input
- prefer fixed scripts with explicit arguments over free-form shell execution

### Safer trigger description pattern
A good description should say:
- what the skill does
- what inputs trigger it
- what it should not be used for
