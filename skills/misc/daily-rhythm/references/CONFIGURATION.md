# Daily Rhythm Configuration Guide

## Overview

Daily Rhythm is a comprehensive daily planning and reflection system that helps you stay focused, track progress, and maintain work-life balance through automated briefings and prompts.

## Features

### Daily Schedule
- **7:00am**: Data sync (Stripe ARR, Google Tasks)
- **8:30am**: Morning Brief with priority, calendar, weather, and tasks
- **10:30pm**: Wind-down prompt to plan tomorrow
- **11:00pm**: Sleep nudge for healthy habits

### Weekly Schedule
- **Sunday 8:00pm**: Weekly review for reflection and planning

## Setup Requirements

### 1. Google Tasks Integration

Required for task syncing:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the **Tasks API**
4. Create OAuth 2.0 credentials (Desktop application)
5. Download `credentials.json`
6. Place in `~/.openclaw/google-tasks/credentials.json`
7. Run `python3 scripts/sync-google-tasks.py` once to authenticate

### 2. Stripe Integration (Optional)

Required for ARR tracking:

1. Get your Stripe API key from [Stripe Dashboard](https://dashboard.stripe.com/apikeys)
2. Create `.env.stripe` in workspace root:
   ```
   STRIPE_API_KEY=sk_live_...
   ```
3. Set ARR target in `memory/heartbeat-state.json`:
   ```json
   {
     "arrTarget": 30000,
     "arrCurrency": "£"
   }
   ```

### 3. Calendar Integration

Add your ICS calendar URL to `TOOLS.md`:
```markdown
### Calendar
- **ICS URL:** `https://calendar.google.com/calendar/ical/...`
```

### 4. Cron Job Setup

Install the cron jobs using your system's cron:

```bash
# Edit crontab
crontab -e

# Add these lines (adjust paths as needed):
0 7 * * * cd /Users/tom/.openclaw/workspace && python3 skills/daily-rhythm/scripts/sync-stripe-arr.py
30 8 * * * cd /Users/tom/.openclaw/workspace && python3 skills/daily-rhythm/scripts/morning-brief.sh
0 20 * * 0 cd /Users/tom/.openclaw/workspace && echo "Weekly review time"
30 22 * * * cd /Users/tom/.openclaw/workspace && echo "Wind-down time"
0 23 * * * cd /Users/tom/.openclaw/workspace && echo "Sleep nudge"
```

Or use OpenClaw's built-in cron system if available.

## Configuration Options

### Daily Intention (Morning Brief Opening)

The morning brief opens with a centering section you can customize to match your beliefs and preferences:

**Examples:**

| Style | Example |
|-------|---------|
| **Faith-based** | "Thank you for already stabilizing my nervous system and guiding my next steps..." |
| **Secular** | "Today I choose to be present, focused, and kind to myself..." |
| **Quote** | "The best time to plant a tree was 20 years ago. The second best time is now." |
| **Intention** | "My intention today is to make progress, not perfection..." |

Edit in `HEARTBEAT.md` under the morning brief section.

### Morning Brief Format

The morning brief includes:
- 🙏 **Daily Intention** — Your prayer, affirmation, quote, or centering thought
- Calendar events
- Focus area
- ARR progress (if Stripe configured)
- Today's priority (from wind-down or top task)
- Actionable suggestions
- Step-by-step plan
- Helpful resources
- Task list
- Weather
- Open loops from yesterday

### Wind-down Priority

When you respond to the 10:30pm prompt, the system:
1. Captures your priority for tomorrow
2. Generates actionable suggestions
3. Breaks it into steps
4. Identifies resources
5. Saves to `memory/YYYY-MM-DD.md`
6. Includes in next morning's brief

### Weekly Review Questions

The Sunday 8pm review asks:

**Where am I?**
- What are you feeling?
- What's bothering you?
- What were this week's wins?
- What's coming up next week?

**What do I do next?**
- What's the big thing to address?
- What are your calendar commitments?
- What can you deprioritize?
- What self-care can you add?

## Customization

### Changing Prayer/Affirmation

Edit the prayer text in the cron job configuration or morning brief script.

### Changing Focus Area

Update the default focus area in `HEARTBEAT.md`:
```markdown
### Focus
Your default focus area here
```

### Adding Custom Sections

Modify the morning brief script to include additional data sources or sections.

### Modifying Times

Adjust cron expressions to change when prompts fire:
- `0 7 * * *` = 7:00am daily
- `30 8 * * *` = 8:30am daily
- `0 20 * * 0` = 8:00pm Sundays
- `30 22 * * *` = 10:30pm daily
- `0 23 * * *` = 11:00pm daily

## File Structure

```
workspace/
├── memory/
│   ├── YYYY-MM-DD.md          # Daily wind-down responses
│   ├── google-tasks.json      # Synced tasks
│   ├── stripe-data.json       # ARR data
│   └── heartbeat-state.json   # Rhythm state
├── skills/daily-rhythm/
│   ├── scripts/
│   │   ├── sync-google-tasks.py
│   │   ├── sync-stripe-arr.py
│   │   └── morning-brief.sh
│   └── references/
│       └── CONFIGURATION.md   # This file
└── HEARTBEAT.md               # Rhythm schedule
```

## Troubleshooting

### Google Tasks Not Syncing
- Check `credentials.json` exists and is valid
- Run sync script manually to see errors
- Verify Tasks API is enabled in Google Cloud

### Stripe ARR Not Showing
- Check `.env.stripe` exists with valid API key
- Verify Stripe account has active subscriptions
- Run sync script manually to see errors

### Cron Jobs Not Firing
- Check cron is installed: `crontab -l`
- Verify paths in cron entries are correct
- Check system logs for errors

### Morning Brief Missing Data
- Ensure sync scripts run successfully
- Check memory files exist and contain data
- Verify file paths in configuration

## Best Practices

1. **Reply to wind-down prompts** for the best morning brief experience
2. **Keep Google Tasks updated** so briefs reflect current priorities
3. **Do weekly reviews** to stay aligned with goals
4. **Customize focus areas** as your priorities change
5. **Adjust timing** to match your natural rhythms

## Support

For issues or feature requests, consult the skill documentation or create an issue in the skill repository.
