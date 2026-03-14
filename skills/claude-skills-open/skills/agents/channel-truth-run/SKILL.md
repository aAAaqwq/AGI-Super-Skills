---
name: channel-truth-run
description: Automatic channel and contact synchronization
---
# Channel Truth Run

> Runs the Channel Truth Agent to synchronize last_contact timestamps

## When to use

- "run channel truth"
- "update last contact dates"
- "synchronize contact dates"
- "run channel truth agent"

## What it does

Channel Truth Agent:
1. Loads all activities from `activities.csv`
2. Finds the most recent communication for each contact
3. (Optionally) Scans channels (Email, Telegram, WhatsApp, LinkedIn)
4. Merges data and resolves conflicts
5. Updates `people.csv`, `leads.csv`, `clients.csv` with current dates
6. Generates a report (stale/hot contacts)
7. Sends summary to Telegram

## How to execute

### Run modes

```bash
# Full run (default)
cd $AGENTS_PATH/channel-truth
python3 channel_truth_agent.py

# Dry-run (read only, no writes)
python3 channel_truth_agent.py --dry-run

# Single contact (for debugging)
python3 channel_truth_agent.py --person-id=p-acme-001

# Without channel scanning (activities.csv only)
python3 channel_truth_agent.py --no-channels
```

### Pre-run checks

```bash
# Check if activities.csv exists
ls -lh $CRM_PATH/activities.csv

# Check people.csv
ls -lh $CRM_PATH/contacts/people.csv

# Dry-run test
python3 channel_truth_agent.py --dry-run
```

### After run

```bash
# View report
ls -lt $AGENTS_PATH/reports/channel_truth_*.md | head -1

# View latest report
cat $(ls -t $AGENTS_PATH/reports/channel_truth_*.md | head -1)

# View logs
tail -20 $AGENTS_PATH/logs/channel_truth.json
```

## Output

1. **Updated CSV files:**
   - `people.csv` - added `last_contact` and `last_updated`
   - `leads.csv` - added `last_contact_via_primary`
   - `clients.csv` - added `last_contact_via_primary`

2. **Report:**
   - `$AGENTS_PATH/reports/channel_truth_YYYY-MM-DD.md`

3. **Backup files:**
   - `people.csv.bak.TIMESTAMP`
   - `leads.csv.bak.TIMESTAMP`
   - `clients.csv.bak.TIMESTAMP`

4. **Telegram notification:**
   - Summary: how many updated, hot/stale contacts

## Rollback

If something went wrong:

```bash
# Rollback via backup
cd $CRM_PATH/contacts/
ls -lt people.csv.bak.* | head -1
cp people.csv.bak.YYYYMMDD_HHMMSS people.csv

cd ../relationships/
cp leads.csv.bak.YYYYMMDD_HHMMSS leads.csv
cp clients.csv.bak.YYYYMMDD_HHMMSS clients.csv

# Or via git
cd $PROJECT_ROOT
git log --oneline sales/crm/
git revert <commit-hash>
```

## Schedule

Agent runs automatically via launchd:
- **Time**: 02:00 daily (after email agent)
- **Plist**: `~/Library/LaunchAgents/com.yourcompany.channel-truth-agent.plist`

```bash
# Check status
launchctl list | grep channel-truth

# Reload
launchctl unload ~/Library/LaunchAgents/com.yourcompany.channel-truth-agent.plist
launchctl load ~/Library/LaunchAgents/com.yourcompany.channel-truth-agent.plist
```

## Troubleshooting

### "activities.csv not found"
```bash
# Check path
ls -l $CRM_PATH/activities.csv

# If missing - create a basic one
echo "activity_id,person_id,company_id,product_id,type,channel,direction,subject,notes,date,created_by" > activities.csv
```

### "Telegram notification failed"
```bash
# Check Telegram credentials
ls -l $SALES_PATH/telegram/sessions/

# Test tg-tools
cd $TG_TOOLS_PATH
python3 -c "from tg_utils.auth import get_client; import asyncio; asyncio.run(get_client())"
```

### "Channel API failure"
```bash
# Skip channel scanning
python3 channel_truth_agent.py --no-channels
```

## Related skills

- `log-activity` - logs activities in activities.csv
- `git-workflow` - for committing changes (if needed)
- `telegram-send` - for manually sending messages

## Usage example

```bash
# User: "run channel truth in dry-run"
cd $AGENTS_PATH/channel-truth
python3 channel_truth_agent.py --dry-run

# View what will be changed
cat /tmp/channel-truth-output.txt

# If everything is ok - run for real
python3 channel_truth_agent.py

# View report
cat $(ls -t $AGENTS_PATH/reports/channel_truth_*.md | head -1)
```

## Notes

- Agent is idempotent (can be run multiple times)
- Always backs up before modifying CSV
- If a channel is unavailable - skips with warning
- activities.csv - primary source of truth
- Channel archives - supplementary (for verification)
