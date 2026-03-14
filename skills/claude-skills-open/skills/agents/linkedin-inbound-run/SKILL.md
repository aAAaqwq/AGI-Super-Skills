---
name: linkedin-inbound-run
description: Automatic inbound LinkedIn message processing
---
# LinkedIn Inbound Run

> Runs the LinkedIn Inbound Agent to monitor incoming messages.

## When to use

- "check LinkedIn messages"
- "run LinkedIn inbound agent"
- "any new messages on LinkedIn?"

## How to execute

### Step 1: Check prerequisites

```bash
# Check that Chrome is running with debugging
lsof -i :9222
# Should show a Chrome process on port 9222

# If Chrome is not running:
$SCRIPTS_PATH/start_chrome_linkedin.sh
```

### Step 2: Run the agent

**Dry-run (no CRM writes, no notifications):**

```bash
cd $AGENTS_PATH/linkedin-inbound
python3 linkedin_inbound_agent.py --dry-run
```

**Full run:**

```bash
cd $AGENTS_PATH/linkedin-inbound
python3 linkedin_inbound_agent.py
```

**Notification test:**

```bash
python3 linkedin_inbound_agent.py --notify-test
```

### Step 3: Check results

```bash
# View summary
today=$(date +%Y-%m-%d)
cat $AGENTS_PATH/logs/linkedin-inbound-$today.md

# View error log
tail -20 $AGENTS_PATH/logs/linkedin_inbound_errors.log

# View agent log
cat $AGENTS_PATH/logs/linkedin_agent_log.json | jq '.[-5:]'
```

### Step 4: Notify the user

- How many messages were processed
- How many new contacts
- How many POSITIVE/QUESTION replies
- Whether manual review is needed

## Output

- **Telegram notification** in Saved Messages (if there are actionable items)
- **Summary log**: `agents/logs/linkedin-inbound-{date}.md`
- **CRM updates**: `sales/crm/activities.csv`, `sales/crm/relationships/leads.csv`
- **Staged contacts**: `sales/crm/staging/linkedin_inbound_new_contacts.csv`

## Errors

### CDP connection failed

```
ERROR: CDP connection failed: ...
```

**Resolution:**
1. Start Chrome with debugging:
   ```bash
   $SCRIPTS_PATH/start_chrome_linkedin.sh
   ```
2. Open LinkedIn: https://www.linkedin.com/messaging/
3. Check login

### Classification failed

Agent automatically switches to fallback classification (rule-based).
Check if Claude CLI works:

```bash
echo "test" | claude -p --model haiku
```

### Telegram failed

Notification text is saved in the log file even if Telegram is not working.

```bash
tail -f /tmp/linkedin-inbound-agent.log
```

## Scheduled run

Agent runs automatically via launchd:

```bash
# Status
launchctl list | grep linkedin-inbound

# Stop
launchctl unload ~/Library/LaunchAgents/com.yourcompany.linkedin-inbound.plist

# Start
launchctl load ~/Library/LaunchAgents/com.yourcompany.linkedin-inbound.plist

# View logs
tail -f /tmp/linkedin-inbound-agent.log
tail -f /tmp/linkedin-inbound-agent-error.log
```

## Related skills

- `change-review` — if a PR with CRM changes is needed
- `add-lead` — add staged contacts to CRM
- `telegram-send` — manually send notification
