---
name: timezone
description: Local time detection, timezone conversion
user-invocable: false
---
# Timezone

> Detecting user's local time at session start

## When to use

- **Always at session start** (automatically via hook or manually)
- When time conversion is needed (calendar, calls, deadlines)
- When Claude displays any time to the user

## How to determine current time

```bash
date '+%Y-%m-%d %H:%M:%S %Z %z'
```

This gives the exact time, timezone and UTC offset from the system clock.

## Rules

1. **NEVER guess the timezone** -- always query the system clock
2. **NEVER convert manually** -- use Python `datetime` with `zoneinfo`
3. **Always display times in the user's local timezone** (determined from the system clock)
4. Google Calendar API returns time in the event creation timezone -- **always convert to local**

## Time conversion (Python)

```python
from datetime import datetime
from zoneinfo import ZoneInfo
import subprocess

# Determine timezone from system
result = subprocess.run(['date', '+%z'], capture_output=True, text=True)
offset = result.stdout.strip()  # e.g. "+0800"

# Or use timezone directly
local_tz = ZoneInfo('Asia/Makassar')  # WITA, UTC+8

# Convert from another timezone
event_time = datetime.fromisoformat('2026-02-16T13:30:00+01:00')  # CET
local_time = event_time.astimezone(local_tz)
print(local_time.strftime('%H:%M %Z'))  # -> 20:30 WITA
```

## Current configuration

- **Location:** Bali, Indonesia
- **Timezone:** WITA (UTC+8), `Asia/Makassar`
- **IMPORTANT:** Indonesia has 3 timezones (WIB +7, WITA +8, WIT +9). Bali = WITA.

## Related skills

- `daily-briefing` -- displays event times
- `show-today` -- deadlines
