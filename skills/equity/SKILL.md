---
name: equity
version: "2.0.0"
author: BytesAgain
homepage: https://bytesagain.com
source: https://github.com/bytesagain/ai-skills
license: MIT-0
tags: [equity, tool, utility]
description: "Model cap tables, dilution scenarios, and vesting schedules for startups. Use when planning fundraising, pricing options, or tracking equity."
---

# Equity

Equity calculator — cap table, dilution modeling, vesting schedules, and option pricing.

## Commands

| Command | Description |
|---------|-------------|
| `equity help` | Show usage info |
| `equity run` | Run main task |
| `equity status` | Check state |
| `equity list` | List items |
| `equity add <item>` | Add item |
| `equity export <fmt>` | Export data |

## Usage

```bash
equity help
equity run
equity status
```

## Examples

```bash
equity help
equity run
equity export json
```

## Output

Results go to stdout. Save with `equity run > output.txt`.

## Configuration

Set `EQUITY_DIR` to change data directory. Default: `~/.local/share/equity/`

---
*Powered by BytesAgain | bytesagain.com*
*Feedback & Feature Requests: https://bytesagain.com/feedback*


## Features

- Simple command-line interface for quick access
- Local data storage with JSON/CSV export
- History tracking and activity logs
- Search across all entries

## Quick Start

```bash
# Check status
equity status

# View help
equity help

# Export data
equity export json
```

## How It Works

Equity stores all data locally in `~/.local/share/equity/`. Each command logs activity with timestamps for full traceability.

## Support

- Feedback: https://bytesagain.com/feedback/
- Website: https://bytesagain.com

Powered by BytesAgain | bytesagain.com | hello@bytesagain.com
