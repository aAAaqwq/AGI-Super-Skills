#!/usr/bin/env bash
# ============================================================================
# inject-worker-skills.sh — Inject skill prompts into Worker worktree
# ============================================================================
# Assembles a CLAUDE.md from skill fragments based on task type.
# Worker (Claude Code / Codex) reads CLAUDE.md automatically on start.
#
# Usage:
#   ./inject-worker-skills.sh <worktree_path> [skill_tags...]
#
# Skill tags:
#   core        — Karpathy 4 principles (always recommended)
#   frontend    — Taste-skill UI/UX quality
#   tdd         — Test-driven development
#   debug       — Systematic debugging
#   verify      — Verification before completion
#   all         — All skills
#
# Examples:
#   ./inject-worker-skills.sh /tmp/orch-fix-nav core           # basic task
#   ./inject-worker-skills.sh /tmp/orch-new-ui core frontend   # UI task
#   ./inject-worker-skills.sh /tmp/orch-bugfix core debug tdd  # debug task
#
# Environment:
#   WORKER_SKILLS_DIR — path to skill fragments (default: script's ../worker-skills/)
# ============================================================================

set -euo pipefail

WORKTREE="${1:?Usage: inject-worker-skills.sh <worktree_path> [skill_tags...]}"
shift
TAGS=("${@:-core}")

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="${WORKER_SKILLS_DIR:-${SCRIPTS_DIR}/../worker-skills}"

CLAUDE_MD="$WORKTREE/CLAUDE.md"

# Start with header
cat > "$CLAUDE_MD" << 'HEADER'
# CLAUDE.md — Worker Engineering Standards

Read this file before starting any work. These are non-negotiable quality standards.

HEADER

# Map tags to files
declare -A SKILL_MAP=(
  [core]="karpathy.md"
  [frontend]="taste-frontend.md"
  [tdd]="tdd.md"
  [debug]="debug.md"
  [debug-tdd]="debug-tdd.md"
  [verify]="verify.md"
  [vercel]="vercel.md"
)

INJECTED=0
for TAG in "${TAGS[@]}"; do
  if [ "$TAG" = "all" ]; then
    for KEY in "${!SKILL_MAP[@]}"; do
      FILE="${SKILLS_DIR}/${SKILL_MAP[$KEY]}"
      if [ -f "$FILE" ]; then
        echo "" >> "$CLAUDE_MD"
        echo "---" >> "$CLAUDE_MD"
        echo "" >> "$CLAUDE_MD"
        cat "$FILE" >> "$CLAUDE_MD"
        INJECTED=$((INJECTED + 1))
      fi
    done
    break
  fi

  FILE="${SKILLS_DIR}/${SKILL_MAP[$TAG]:-}"
  if [ -n "$FILE" ] && [ -f "$FILE" ]; then
    echo "" >> "$CLAUDE_MD"
    echo "---" >> "$CLAUDE_MD"
    echo "" >> "$CLAUDE_MD"
    cat "$FILE" >> "$CLAUDE_MD"
    INJECTED=$((INJECTED + 1))
  else
    echo "WARN: Unknown skill tag '$TAG' or file not found" >&2
  fi
done

# Add CLAUDE.md to worktree exclude (avoid dirty main repo)
GIT_DIR=$(git -C "$WORKTREE" rev-parse --git-dir 2>/dev/null || echo "")
if [ -n "$GIT_DIR" ]; then
  mkdir -p "$GIT_DIR/info"
  touch "$GIT_DIR/info/exclude"
  grep -q "CLAUDE.md" "$GIT_DIR/info/exclude" 2>/dev/null || echo "CLAUDE.md" >> "$GIT_DIR/info/exclude"
fi

echo "{\"injected\":$INJECTED,\"tags\":[$(printf '"%s",' "${TAGS[@]}" | sed 's/,$//')]}"
