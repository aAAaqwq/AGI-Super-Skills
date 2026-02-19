# Daily Rhythm

Transform your daily routine with automated morning briefs, evening wind-down prompts, and weekly reviews. Stay focused, track progress, and maintain work-life balance without the mental overhead.

## What It Does

Daily Rhythm creates a structured daily planning system that runs automatically:

**☀️ Morning Brief (8:30am)**
- Daily intention (prayer, affirmation, or centering thought)
- Calendar events
- Today's priority with actionable steps
- Task list from Google Tasks
- Weather
- Progress tracking (optional Stripe ARR)

**🌙 Wind-Down Prompt (10:30pm)**
- Plan tomorrow's priority
- Get actionable suggestions
- Break goals into steps
- Auto-saves to tomorrow's brief

**😴 Sleep Nudge (11:00pm)**
- Gentle reminder to rest
- Encouraging words for tomorrow

**📅 Weekly Review (Sunday 8pm)**
- Reflect on the week
- Celebrate wins
- Identify blockers
- Create tasks for the week ahead

## Quick Start

1. **Install** the skill
2. **Configure Google Tasks** (required)
   - Get API credentials from Google Cloud
   - Place `credentials.json` in `~/.openclaw/google-tasks/`
3. **Optional**: Add Stripe API key for ARR tracking
4. **Optional**: Add calendar ICS URL
5. **Set up cron jobs** or use OpenClaw's cron system
6. **Customize** your Daily Intention in HEARTBEAT.md
7. **Enjoy** automated briefings!

## Perfect For

- **Founders** tracking ARR while managing daily priorities
- **Professionals** juggling multiple projects
- **Anyone** wanting structured daily planning without the setup work
- **People** who want to start and end their day with intention

## Customization

The "Daily Intention" section is fully customizable:
- **Faith-based**: Prayers, scripture, devotional thoughts
- **Secular**: Affirmations, gratitude practice, intentions
- **Philosophy**: Stoic quotes, mindful centering
- **Personal**: Mission statements, core values

## Requirements

- Python 3.7+
- Google Tasks API credentials
- Optional: Stripe API key (for ARR tracking)
- Optional: Calendar ICS URL

## What's Included

- Google Tasks sync script
- Stripe ARR calculator
- Morning brief generator
- Wind-down response handler
- Weekly review system
- Complete setup documentation

---

*Start each day with clarity. End each day with peace.*
