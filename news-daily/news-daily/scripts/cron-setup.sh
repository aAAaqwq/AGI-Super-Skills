#!/bin/bash
# Cron Job Setup Script for News Daily
# This script helps configure automated news delivery schedules

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FETCHER_SCRIPT="$SCRIPT_DIR/news-fetcher.sh"
LOG_DIR="/home/aa/clawd/logs"

echo "📰 News Daily - Cron Job Setup"
echo "================================"
echo ""

# Check if fetcher script exists
if [ ! -f "$FETCHER_SCRIPT" ]; then
  echo "❌ ERROR: News fetcher script not found at $FETCHER_SCRIPT"
  exit 1
fi

# Create log directory
echo "📁 Creating log directory: $LOG_DIR"
mkdir -p "$LOG_DIR"

# Get current crontab
echo ""
echo "Current crontab:"
crontab -l 2>/dev/null || echo "(no existing crontab)"
echo ""

# Ask for schedule preference
echo "Select schedule:"
echo "1) All three reports (Morning: 8:00, Afternoon: 13:00, Evening: 18:00)"
echo "2) Morning only (8:00)"
echo "3) Morning and Evening (8:00, 18:00)"
echo "4) Custom schedule"
echo -n "Enter choice [1-4]: "
read choice

case "$choice" in
  1)
    echo "Setting up all three reports..."
    SCHEDULES=(
      "0 8 * * * $FETCHER_SCRIPT --push telegram >> $LOG_DIR/news-morning.log 2>&1"
      "0 13 * * * $FETCHER_SCRIPT --push telegram >> $LOG_DIR/news-afternoon.log 2>&1"
      "0 18 * * * $FETCHER_SCRIPT --push telegram >> $LOG_DIR/news-evening.log 2>&1"
    )
    ;;
  2)
    echo "Setting up morning report only..."
    SCHEDULES=(
      "0 8 * * * $FETCHER_SCRIPT --push telegram >> $LOG_DIR/news-morning.log 2>&1"
    )
    ;;
  3)
    echo "Setting up morning and evening reports..."
    SCHEDULES=(
      "0 8 * * * $FETCHER_SCRIPT --push telegram >> $LOG_DIR/news-morning.log 2>&1"
      "0 18 * * * $FETCHER_SCRIPT --push telegram >> $LOG_DIR/news-evening.log 2>&1"
    )
    ;;
  4)
    echo "Custom schedule setup"
    echo "Enter cron schedules (one per line, empty line to finish):"
    echo "Format: minute hour day month weekday command"
    echo "Example: 0 8 * * * $FETCHER_SCRIPT --push telegram"
    SCHEDULES=()
    while true; do
      echo -n "cron> "
      read line
      [ -z "$line" ] && break
      SCHEDULES+=("$line >> $LOG_DIR/news-custom.log 2>&1")
    done
    ;;
  *)
    echo "❌ Invalid choice"
    exit 1
    ;;
esac

# Ask for push channel
echo ""
echo -n "Push channel [telegram/whatsapp] (default: telegram): "
read channel
channel=${channel:-telegram}

# Update schedules with channel
UPDATED_SCHEDULES=()
for schedule in "${SCHEDULES[@]}"; do
  UPDATED_SCHEDULES+=("${schedule/--push telegram/--push $channel}")
  UPDATED_SCHEDULES+=("${schedule/--push whatsapp/--push $channel}")
done
SCHEDULES=("${UPDATED_SCHEDULES[@]}")

# Display what will be added
echo ""
echo "Cron jobs to be added:"
for schedule in "${SCHEDULES[@]}"; do
  echo "  $schedule"
done
echo ""

# Confirm
echo -n "Add these to crontab? [y/N]: "
read confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
  # Add to crontab
  (crontab -l 2>/dev/null; echo ""; for schedule in "${SCHEDULES[@]}"; do echo "$schedule"; done) | crontab -
  echo "✅ Cron jobs installed successfully!"
  echo ""
  echo "Current crontab:"
  crontab -l
else
  echo "❌ Cancelled"
  exit 0
fi

# Test run
echo ""
echo -n "Run test fetch now? [y/N]: "
read test_run
if [[ "$test_run" =~ ^[Yy]$ ]]; then
  echo "Running test fetch..."
  "$FETCHER_SCRIPT" --push "$channel"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To view logs: tail -f $LOG_DIR/news-*.log"
echo "To edit crontab: crontab -e"
echo "To remove jobs: crontab -e (delete the relevant lines)"
