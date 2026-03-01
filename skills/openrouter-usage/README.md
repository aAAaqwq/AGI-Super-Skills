# openrouter-usage

An [OpenClaw](https://github.com/openclaw/openclaw) skill to track your OpenRouter API spending.

## Features

- **Full spending report** — Credit balance + per-model breakdown + projection in one command
- **Per-model cost breakdown** — Cost, tokens, cache stats per model from session logs
- **Date filtering** — `--today`, `--week`, `--month`, `--date`, `--from/--to`
- **Spending projection** — Estimates how long your credits will last
- **Multi-agent support** — Filter by agent with `--agent`
- **Local timezone** — Date filters use your local timezone by default
- **JSON output** — Machine-readable output for automation
- **Zero dependencies** — Python 3 stdlib only
- **Auto key discovery** — Reads API key from env var or OpenClaw auth store

## Install

**ClawHub:** [lcajigasm/openrouter-usage-info](https://clawhub.ai/lcajigasm/openrouter-usage-info)

### From ClawHub

```bash
clawhub install lcajigasm/openrouter-usage-info
```

### From source

```bash
git clone https://github.com/ZarpAIbot/openrouter-usage
cd openrouter-usage
./install.sh
```

The installer will:
1. Create a `openrouter-usage` CLI wrapper in `~/.local/bin/`
2. Optionally link it as an OpenClaw workspace skill
3. Warn you if `~/.local/bin` isn't in your PATH

## Usage

```bash
# Full report: credits + today's usage + projection
openrouter-usage report

# Report for a different period
openrouter-usage report --week
openrouter-usage report --month

# Credit balance only
openrouter-usage credits

# Per-model breakdown with various date filters
openrouter-usage sessions --today
openrouter-usage sessions --week
openrouter-usage sessions --month
openrouter-usage sessions --date 2026-02-25
openrouter-usage sessions --from 2026-02-01 --to 2026-02-15

# Filter by agent
openrouter-usage report --agent main

# JSON output
openrouter-usage report --format json

# Use UTC instead of local timezone
openrouter-usage report --today --utc
```

### Example output

```
═══ OpenRouter Credits ═══
  Total:      $10.0000
  Used:       $2.3200
  Remaining:  $7.6800
  Usage:      23.2%

═══ Usage by Model (today) ═══

  openai/gpt-5.2-chat
    Cost: $0.1823 (78.5%)  |  Requests: 42
    Tokens: 128,450 in / 34,200 out
    Cache: 89,000 read / 12,300 write

  google/gemini-2.0-flash
    Cost: $0.0498 (21.5%)  |  Requests: 15
    Tokens: 45,600 in / 12,800 out

  ──────────────────────────────
  TOTAL: $0.2321  |  57 requests  |  221,050 tokens

📊 Projection: ~$0.2321/day avg → credits last ~33 days
```

## API Key

The script looks for your OpenRouter API key in this order:
1. `OPENROUTER_API_KEY` environment variable
2. OpenClaw agent auth store (`~/.openclaw/agents/*/agent/auth.json`)

If you use OpenClaw with OpenRouter, the key is already configured — no extra setup needed.

## How it works

- **`credits`** — Calls OpenRouter's `/api/v1/credits` endpoint (falls back to `/api/v1/auth/key`)
- **`sessions`** — Parses OpenClaw's session JSONL files locally (no API calls). Extracts `usage.cost` data that OpenRouter includes in every completion response.
- **`report`** — Runs both, adds a daily spending projection based on your historical average.

## Compatibility

- Python 3.8+
- OpenClaw 2026.2.x+ (tested with v2026.2.23)
- macOS, Linux (anywhere Python 3 runs)

## License

MIT
