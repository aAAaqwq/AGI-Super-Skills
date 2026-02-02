# News Daily Installation Guide

## Quick Setup

### 1. Manual Test Run

Test the news fetcher manually first:

```bash
cd /home/aa/clawd/skills/news-daily/news-daily
./scripts/news-fetcher.sh --help

# Test fetch without pushing
./scripts/news-fetcher.sh

# Test fetch with Telegram push
./scripts/news-fetcher.sh --push telegram
```

### 2. Automated Cron Setup

Use the interactive cron setup script:

```bash
./scripts/cron-setup.sh
```

This will guide you through:
- Choosing your schedule (morning/afternoon/evening)
- Selecting push channel (Telegram/WhatsApp)
- Installing cron jobs
- Running a test fetch

### 3. Manual Cron Setup

If you prefer manual setup, edit your crontab:

```bash
crontab -e
```

Add these lines (adjust times for your timezone):

```bash
# Morning news - 8:00 AM
0 8 * * * /home/aa/clawd/skills/news-daily/news-daily/scripts/news-fetcher.sh --push telegram >> /home/aa/clawd/logs/news-morning.log 2>&1

# Afternoon news - 1:00 PM
0 13 * * * /home/aa/clawd/skills/news-daily/news-daily/scripts/news-fetcher.sh --push telegram >> /home/aa/clawd/logs/news-afternoon.log 2>&1

# Evening news - 6:00 PM
0 18 * * * /home/aa/clawd/skills/news-daily/news-daily/scripts/news-fetcher.sh --push telegram >> /home/aa/clawd/logs/news-evening.log 2>&1
```

## Configuration

### Push Channel Settings

Edit `scripts/config.sh`:

```bash
# Default push channel
DEFAULT_CHANNEL="telegram"  # or "whatsapp"

# Optional: Specify chat/contact IDs
TELEGRAM_CHAT_ID=""
WHATSAPP_CONTACT_ID=""
```

### News Sources

Edit `scripts/news-sources.conf` to add/remove sources:

```
# Format: NAME|URL|METHOD|PRIORITY|SELECTOR
机器之心|https://www.jiqizhixin.com/|web_search|10|ai
```

### Summary Style

Edit `scripts/news-summarizer.md` to customize:
- Article selection criteria
- Summary format
- Language style
- Emoji usage

## Troubleshooting

### Script not found in cron

**Problem:** Cron fails with "command not found"

**Solution:** Use absolute paths in crontab:
```bash
/home/aa/clawd/skills/news-daily/news-daily/scripts/news-fetcher.sh
```

### No push notifications

**Problem:** Script runs but no messages sent

**Solution:**
1. Check message tool is configured: `openclaw message --help`
2. Verify channel credentials in `scripts/config.sh`
3. Check logs: `tail -f /home/aa/clawd/logs/news-*.log`

### Timezone issues

**Problem:** News arrives at wrong time

**Solution:**
- Cron uses server local time
- Check timezone: `date`
- Adjust cron hours accordingly

### Permissions errors

**Problem:** Script can't write logs or cache

**Solution:**
```bash
chmod +x scripts/news-fetcher.sh
chmod +x scripts/cron-setup.sh
mkdir -p /home/aa/clawd/logs
```

## Monitoring

### View logs

```bash
# All news logs
ls -lh /home/aa/clawd/logs/news-*.log

# Latest logs
tail -f /home/aa/clawd/logs/news-morning.log
```

### Check cron status

```bash
# List cron jobs
crontab -l

# Check cron logs
grep CRON /var/log/syslog | tail -20
```

### Test manually

```bash
# Test morning schedule
./scripts/news-fetcher.sh --push telegram

# Test with custom article count
./scripts/news-fetcher.sh --push telegram --articles 7

# Test specific sources
./scripts/news-fetcher.sh --push telegram --sources "机器之心,TechCrunch"
```

## Advanced Usage

### Custom schedules

```bash
# Every 6 hours
0 */6 * * * /path/to/news-fetcher.sh --push telegram

# Weekdays only
0 8 * * 1-5 /path/to/news-fetcher.sh --push telegram

# Weekend digest
0 10 * * 6,0 /path/to/news-fetcher.sh --push telegram --articles 10
```

### Multiple channels

```bash
# Push to both Telegram and WhatsApp
0 8 * * * /path/to/news-fetcher.sh --push telegram
5 8 * * * /path/to/news-fetcher.sh --push whatsapp
```

### Custom log locations

Edit `scripts/config.sh`:
```bash
LOG_DIR="/var/log/news-daily"
```

Ensure the directory exists and is writable:
```bash
sudo mkdir -p /var/log/news-daily
sudo chown $USER:$USER /var/log/news-daily
```

## Uninstallation

Remove cron jobs:
```bash
crontab -e
# Delete the news-daily lines
```

Or remove all:
```bash
crontab -r  # Removes entire crontab - be careful!
```

Remove files (optional):
```bash
rm -rf /home/aa/clawd/skills/news-daily
rm -rf /home/aa/clawd/logs/news-*.log
```

## Support

For issues or questions:
1. Check logs: `/home/aa/clawd/logs/news-*.log`
2. Test manually: `./scripts/news-fetcher.sh --push telegram`
3. Verify configuration in `scripts/config.sh`
4. Check cron: `crontab -l` and `grep CRON /var/log/syslog`
