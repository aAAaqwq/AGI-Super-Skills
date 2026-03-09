#!/usr/bin/env bash
# sync.sh - Deploy last30days skill to all host locations
# Usage: bash scripts/sync.sh  (run from repo root)
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
echo "Source: $SRC"

TARGETS=(
  "$HOME/.claude/skills/last30days"
  "$HOME/.claude/skills/last30daysCROSS"
  "$HOME/.agents/skills/last30days"
  "$HOME/.codex/skills/last30days"
)

for t in "${TARGETS[@]}"; do
  echo ""
  echo "--- Syncing to $t ---"
  mkdir -p "$t/scripts/lib"

  # SKILL.md — CROSS gets patched frontmatter + skill root, others get verbatim copy
  if [[ "$t" == *"last30daysCROSS"* ]]; then
    sed \
      -e 's/^name: last30days$/name: last30daysCROSS/' \
      -e 's/^version: "2\.1"/version: "2.2-cross"/' \
      -e "s|^description: .*|description: \"TEST BUILD with outcome-aware Polymarket scoring + cross-source linking. Research a topic from the last 30 days. Sources: Reddit, X, YouTube, Hacker News, Polymarket, web.\"|" \
      -e "s/^argument-hint: .*/argument-hint: 'last30daysCROSS AI video tools'/" \
      -e 's|"\$HOME/.claude/skills/last30days"|"$HOME/.claude/skills/last30daysCROSS" \\\n  "$HOME/.claude/skills/last30days"|' \
      "$SRC/SKILL.md" > "$t/SKILL.md"
  else
    cp "$SRC/SKILL.md" "$t/"
  fi

  # Main script + lib modules (rsync handles identical files gracefully)
  rsync -a "$SRC/scripts/last30days.py" "$t/scripts/"
  rsync -a "$SRC/scripts/lib/"*.py "$t/scripts/lib/"

  # Vendor directory (bird-search CLI)
  if [ -d "$SRC/scripts/lib/vendor" ]; then
    rsync -a "$SRC/scripts/lib/vendor" "$t/scripts/lib/"
  fi

  # Fixtures
  if [ -d "$SRC/fixtures" ]; then
    mkdir -p "$t/fixtures"
    rsync -a "$SRC/fixtures/" "$t/fixtures/"
  fi

  # Count and report
  mod_count=$(ls "$t/scripts/lib/"*.py 2>/dev/null | wc -l | tr -d ' ')
  echo "  Copied $mod_count modules"

  # Verify imports
  if (cd "$t/scripts" && python3 -c "from lib import youtube_yt, bird_x, render, ui; print('  Import check: OK')" 2>&1); then
    true
  else
    echo "  Import check FAILED"
  fi
done

echo ""
echo "Sync complete."
