---
name: self-improving-legal
description: "Injects legal self-improvement reminder during agent bootstrap"
metadata: {"openclaw":{"emoji":"⚖️","events":["agent:bootstrap"]}}
---

# Legal Self-Improvement Hook

Injects a reminder to evaluate legal findings during agent bootstrap.

## What It Does

- Fires on `agent:bootstrap` (before workspace files are injected)
- Adds a reminder block to check `.learnings/` for legal-relevant entries
- Prompts the agent to log clause risks, compliance gaps, contract deviations, and regulatory changes
- Emphasizes **NEVER logging privileged attorney-client communications, case strategy, or confidential settlement terms**
- Reminds to abstract all entries to process-level lessons

## Configuration

No configuration needed. Enable with:

```bash
openclaw hooks enable self-improving-legal
```
