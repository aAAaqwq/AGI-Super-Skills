---
name: model-usage-linux
description: "Track OpenClaw AI token usage and cost per model on Linux by parsing session JSONL files. Use when asked about: token usage, API cost, how much has been spent, which model was used most, usage summary, billing, cost breakdown. Linux replacement for the macOS-only model-usage/CodexBar skill."
---

# Model Usage (Linux)

Parse OpenClaw session files to summarize token usage and cost per model.

## Quick start

```bash
python3 {baseDir}/scripts/usage.py
```

## Options

```bash
# JSON output
python3 {baseDir}/scripts/usage.py --format json

# Custom sessions dir
python3 {baseDir}/scripts/usage.py --sessions-dir ~/.openclaw/agents/main/sessions
```

## Output

Shows per-model breakdown:
- Turns (assistant replies)
- Input / output tokens
- Cache read / write tokens
- Cost in USD

Sessions live at: `~/.openclaw/agents/main/sessions/*.jsonl`
