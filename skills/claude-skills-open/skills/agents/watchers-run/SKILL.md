---
name: watchers-run
description: Automatic trigger monitoring for leads
---
# Watchers Agent - Run Skill

> Manual run of the website change monitoring agent

## When to use

- "run watchers"
- "check website changes"
- "run website monitoring"
- Testing after configuration change

## What it does

Watchers Agent monitors target websites (competitors, clients, partners) for changes and sends Telegram notifications when important updates are detected.

## How to execute

### 1. Full run (production)

```bash
cd $AGENTS_PATH/watchers
python3 watchers_agent.py
```

**What happens:**
- Loads configuration
- Checks targets that are due for checking (by last_checked)
- Downloads content and compares with saved snapshots
- Uses Claude Haiku to filter noise
- Sends Telegram notifications about important changes
- Updates state files

### 2. Dry-run (testing)

```bash
cd $AGENTS_PATH/watchers
python3 watchers_agent.py --dry-run
```

**Use for:**
- Testing after configuration change
- Checking new targets
- Debugging without sending notifications
- Previewing what would be detected

**What does NOT happen:**
- Does not update state files
- Does not send Telegram notifications
- Only shows what would have been done

### 3. Configuration check

```bash
cd $AGENTS_PATH/watchers
python3 watchers_agent.py --validate-config
```

Checks YAML syntax and outputs a list of enabled/disabled targets.

**Use before:**
- Adding new targets
- Changing selectors or thresholds
- First agent run

### 4. Telegram test

```bash
cd $AGENTS_PATH/watchers
python3 watchers_agent.py --notify-test
```

Sends a test notification to verify Telegram integration.

### 5. State reset

```bash
# Preview
python3 watchers_agent.py --reset-state --dry-run

# Actual reset (confirmation required)
python3 watchers_agent.py --reset-state
```

**When to use:**
- After major configuration changes (new selectors)
- If state files are corrupted
- To re-baseline all targets

**WARNING:** The next run after reset will treat all targets as new and may send many alerts.

## Configuration

### Configuration file

`$PROJECT_ROOT/monitoring/watchers/watcher_config.yaml`

### Target example

```yaml
watchers:
  - name: "Competitor Careers Page"
    url: "https://competitor.com/careers"
    type: webpage
    selector: "div.job-listings"  # CSS selector
    priority: high                 # low|medium|high
    check_interval: "1h"           # "1h", "4h", "24h"
    change_threshold: 5            # % change for alert
    tags: ["competitor", "hiring"]
    related_crm_id: "comp-competitor-001"
    enabled: true
```

### Adding a new target

1. Open `watcher_config.yaml`
2. Add a new element to the `watchers` list
3. Find the correct CSS selector (DevTools -> Inspect)
4. Set `enabled: true`
5. Run `--validate-config` to check
6. Run `--dry-run` for testing
7. Run without flags for production

## Output

### Console

```
[2026-02-12 10:00:00] Loading configuration...
[2026-02-12 10:00:00] Found 5 target(s) due for checking
[2026-02-12 10:00:01] Processing [1/5]: Competitor Careers Page
[2026-02-12 10:00:03]   CHANGE DETECTED: 12.3% (modified_content)
[2026-02-12 10:00:05]   MEANINGFUL: job_posting - New position posted
[2026-02-12 10:00:10] Done: 5 checked, 2 changed, 1 alerts, 0 errors
```

### Telegram Alert

```
🔥 URGENT - Website Change Alert

**Competitor Careers Page**
https://competitor.com/careers

Category: Job Posting
Tags: competitor, hiring
Change: 12.3%

New senior engineer position posted for ML team

Diff preview:
```
+ Senior ML Engineer - Remote
+ We are hiring a senior engineer to join our ML team...
```

💡 Outreach Trigger Detected
Suggested action: Review competitor hiring activity
Related CRM: comp-competitor-001
```

### State Files

`$PROJECT_ROOT/monitoring/watchers/state/competitor_com_careers.json`

```json
{
  "last_checked": "2026-02-12T10:00:00",
  "content_hash": "abc123...",
  "content_text": "Full page content...",
  "metadata": {
    "word_count": 1523,
    "fetch_timestamp": "2026-02-12T10:00:00",
    "http_status": 200
  },
  "failure_count": 0,
  "last_alert_sent": "2026-02-12T10:00:00"
}
```

## Troubleshooting

### "Selector not found"

CSS selector was not found on the page.

**Fix:**
1. Open URL in browser
2. Right-click -> Inspect -> find the correct element
3. Update `selector` in config

### Too many false positives

Changes detected but not meaningful (timestamps, view counts).

**Fix:**
1. Use a more specific selector (exclude dynamic content)
2. Increase `change_threshold` for noisy targets
3. AI filtering should filter these automatically

### Telegram not working

**Check:**
1. Run `--notify-test`
2. Check tg-tools session files
3. Look at stderr logs
4. Check `pending_alerts.txt` for failed alerts

### Missed changes

Changes occurred but no alert was sent.

**Check:**
1. `enabled: true` in config?
2. Change >= `change_threshold`? Decrease threshold
3. AI filter rejected as noise? Check state file diff
4. Check `watcher_log.json` for errors

## Emergency Stop

If the agent is flooding Telegram:

```bash
# Create PAUSE file
touch $PROJECT_ROOT/monitoring/watchers/PAUSE

# Agent will skip the next run

# Remove PAUSE to resume
rm $PROJECT_ROOT/monitoring/watchers/PAUSE
```

## Scheduling (launchd)

### Install

```bash
cp $AGENTS_PATH/watchers/com.yourcompany.watchers-agent.plist \
   ~/Library/LaunchAgents/

launchctl load ~/Library/LaunchAgents/com.yourcompany.watchers-agent.plist
```

### Check Status

```bash
launchctl list | grep watchers
```

### View Logs

```bash
# stdout
tail -f /tmp/watchers-agent.log

# stderr (main logs here)
tail -f /tmp/watchers-agent-error.log
```

### Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.yourcompany.watchers-agent.plist
rm ~/Library/LaunchAgents/com.yourcompany.watchers-agent.plist
```

## Files

| File | Purpose |
|------|---------|
| `watchers_agent.py` | Main script |
| `watcher_config.yaml` | Configuration |
| `watcher_log.json` | Run history (last 100) |
| `pending_alerts.txt` | Failed alerts fallback |
| `state/*.json` | State files per target |
| `PAUSE` | Emergency stop (create to pause) |

## Related

- **Email Agent** (`$GOOGLE_TOOLS_PATH/email_agent.py`) - similar pattern
- **Daily Briefing** (future) - will include watcher alerts
- **CRM Add/Update** (future) - auto-create tasks on triggers
- **Touch Scheduler** (future) - schedule follow-ups

## Owner

Your Name (your@email.com)
