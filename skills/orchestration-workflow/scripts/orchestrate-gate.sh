#!/usr/bin/env bash
# orchestrate-gate.sh — Run gate check + merge + deploy + cleanup for a completed task
#
# Usage: orchestrate-gate.sh <task-id>
#
# Called by orchestrate-patrol.sh when worker is done.
# Reads state from /tmp/orch-tasks/<task-id>.state.
#
# Exit codes:
#   10 = gate passed, merge + deploy done
#   20 = gate failed
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
SSH_TMUX=""
for p in \
  "${SCRIPTS_DIR}/../../../persistent-ssh-tmux/scripts/ssh_tmux_session.sh" \
  "$HOME/.openclaw/skills/persistent-ssh-tmux/scripts/ssh_tmux_session.sh" \
  "$HOME/.agents/skills/persistent-ssh-tmux/scripts/ssh_tmux_session.sh"; do
  [ -f "$p" ] && SSH_TMUX="$p" && break
done
TASK_DIR="/tmp/orch-tasks"

tmux_kill() {
  if [ "$HOST" = "localhost" ]; then
    tmux kill-session -t "$1" 2>/dev/null || true
  else
    bash "$SSH_TMUX" "$HOST" "$1" kill --quiet 2>/dev/null || true
  fi
}

TASK_ID="${1:?Usage: orchestrate-gate.sh <task-id>}"
STATE_FILE="${TASK_DIR}/${TASK_ID}.state"

# Read state — single python3 call
eval "$(python3 -c "
import json
s = json.load(open('$STATE_FILE'))
for k in ['repo','worktree','branch','host','session','baseline']:
    print(f\"{k.upper()}={s[k]!r}\")
print(f\"DEPLOY={s['deploy']}\")
print(f\"CLEANUP={s['cleanup']}\")
print(f\"AI_REVIEW={s.get('ai_review',0)}\")
print(f\"MAX_RETRIES={s.get('max_retries',3)}\")
print(f\"RESULT_JSON={json.dumps(s.get('result',{}))!r}\")
")"

MAX_FILES=${MAX_FILES:-5}
AI_REVIEW=${AI_REVIEW:-0}
MAX_RETRIES=${MAX_RETRIES:-3}

log() { echo "{\"phase\":\"$1\",\"status\":\"$2\",\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"task\":\"$TASK_ID\"${3:+,$3}}"; }

rcmd() {
  if [ "$HOST" = "localhost" ]; then eval "$1"; else ssh "$HOST" "$1"; fi
}

# ============================================================================
# Gate checks
# ============================================================================
GATE_PASS=1
GATE_REASON=""

# Parse result
STATUS=$(echo "$RESULT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
BUILD=$(echo "$RESULT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('build_pass','null'))" 2>/dev/null || echo "null")
COMMIT=$(echo "$RESULT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('commit','null'))" 2>/dev/null || echo "null")

if [ "$STATUS" != "success" ] && [ "$STATUS" != "completed" ] && [ "$STATUS" != "done" ]; then
  GATE_PASS=0; GATE_REASON="status_not_success"
elif [ "$COMMIT" = "null" ] || [ "$COMMIT" = "None" ] || [ -z "$COMMIT" ]; then
  # Worker may have written result.json but not committed — check git and auto-commit if dirty
  ACTUAL_HEAD=$(rcmd "cd '$WORKTREE' && git rev-parse --short HEAD 2>/dev/null" || echo "$BASELINE")
  if [ "$ACTUAL_HEAD" != "$BASELINE" ]; then
    # Worker did commit, just didn't report it in result JSON
    COMMIT="$ACTUAL_HEAD"
    log "gate" "commit_found" "\"commit\":\"$COMMIT\",\"note\":\"not in result.json\""
  else
    # Check for dirty files — auto-commit if present
    DIRTY=$(rcmd "cd '$WORKTREE' && git status --porcelain 2>/dev/null | wc -l | tr -d ' '" || echo "0")
    if [ "$DIRTY" -gt 0 ]; then
      log "gate" "auto_commit" "\"dirty\":$DIRTY"
      rcmd "cd '$WORKTREE' && git add -A && git reset HEAD -- .task-prompt.md .task-result.json .orch-setup-done CLAUDE.md 2>/dev/null; git commit -m 'feat: ${TASK_ID} (gate auto-commit)'" 2>/dev/null || true
      COMMIT=$(rcmd "cd '$WORKTREE' && git rev-parse --short HEAD 2>/dev/null" || echo "")
      if [ "$COMMIT" = "$BASELINE" ] || [ -z "$COMMIT" ]; then
        GATE_PASS=0; GATE_REASON="auto_commit_failed"
      fi
    else
      GATE_PASS=0; GATE_REASON="no_commit_no_changes"
    fi
  fi
fi

# Build check (run ourselves if unknown)
if [ "$GATE_PASS" = "1" ]; then
  if [ "$BUILD" = "False" ] || [ "$BUILD" = "false" ]; then
    GATE_PASS=0; GATE_REASON="build_failed"
  elif [ "$BUILD" = "null" ] || [ "$BUILD" = "None" ]; then
    log "gate" "build_check" "\"reason\":\"running_build\""
    if (rcmd "cd '$WORKTREE' && npm run build") >/dev/null 2>&1; then
      BUILD="true"
    else
      GATE_PASS=0; GATE_REASON="build_failed_on_gate_check"
    fi
  fi
fi

# File count check
if [ "$GATE_PASS" = "1" ]; then
  FILE_COUNT=$(rcmd "cd '$WORKTREE' && git diff --name-only '$BASELINE' 2>/dev/null | grep -vE '^(\.task-prompt\.md|\.task-result\.json|\.orch-setup-done|CLAUDE\.md|package\.json|package-lock\.json)$' | wc -l | tr -d ' '" 2>/dev/null || echo "0")
  FILE_COUNT=$(echo "$FILE_COUNT" | tr -d ' ')
  if [ "$FILE_COUNT" -gt "$MAX_FILES" ] 2>/dev/null; then
    GATE_PASS=0; GATE_REASON="too_many_files (${FILE_COUNT}>${MAX_FILES})"
  fi
fi

# needs_split check
NEEDS_SPLIT=$(echo "$RESULT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('needs_split', False))" 2>/dev/null || echo "False")
if [ "$NEEDS_SPLIT" = "True" ] || [ "$NEEDS_SPLIT" = "true" ]; then
  GATE_PASS=0; GATE_REASON="needs_split"
fi

# Env var detection (warning only)
if [ "$GATE_PASS" = "1" ]; then
  NEW_ENVS=$(rcmd "cd '$WORKTREE' && git diff '$BASELINE' -- . ':(exclude).task-prompt.md' ':(exclude).task-result.json' ':(exclude)CLAUDE.md' 2>/dev/null | grep -oE 'process\.env\.[A-Z_]+' | sort -u" 2>/dev/null || echo "")
  if [ -n "$NEW_ENVS" ]; then
    log "gate" "env_var_warning" "\"new_env_refs\":\"$NEW_ENVS\""
  fi
fi

# ============================================================================
# Gate decision
# ============================================================================
if [ "$GATE_PASS" = "0" ]; then
  # Read retry count
  RETRY_COUNT=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('retry_count',0))" 2>/dev/null || echo "0")
  MAX_RETRIES=${MAX_RETRIES:-3}
  
  # Retryable failures: build_failed, build_failed_on_gate_check
  RETRYABLE=0
  case "$GATE_REASON" in
    build_failed*) RETRYABLE=1 ;;
    status_not_success) RETRYABLE=1 ;;
  esac
  
  if [ "$RETRYABLE" = "1" ] && [ "$RETRY_COUNT" -lt "$MAX_RETRIES" ]; then
    RETRY_COUNT=$((RETRY_COUNT + 1))
    log "gate" "retry" "\"reason\":\"$GATE_REASON\",\"attempt\":$RETRY_COUNT,\"max\":$MAX_RETRIES"
    
    # Generate retry prompt with failure context
    RETRY_PROMPT="$WORKTREE/.task-prompt.md"
    cat >> "$RETRY_PROMPT" << RETRYEOF

## RETRY (Attempt $RETRY_COUNT/$MAX_RETRIES)
Previous attempt failed: **$GATE_REASON**
$(rcmd "cd '$WORKTREE' && npm run build 2>&1 | tail -20" 2>/dev/null || echo "No build output available")

**Fix the build error above.** Focus only on the failing files. Do NOT start over.
When done, write .task-result.json and commit all changes.
RETRYEOF
    
    # Reset state for retry — keep worktree, relaunch Worker
    python3 -c "
import json; s = json.load(open('$STATE_FILE'))
s['status'] = 'running'; s['retry_count'] = $RETRY_COUNT
s['idle_count'] = 0; s['patrol_count'] = 0; s['prev_file_hash'] = ''
json.dump(s, open('$STATE_FILE','w'), indent=2)
"
    # Kill old agent, relaunch
    tmux_kill "$SESSION"
    if [ "$HOST" = "localhost" ]; then
      tmux new-session -d -s "$SESSION"
      YOLO_FLAG=""; [ "$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('yolo',0))")" = "1" ] && YOLO_FLAG="--full-auto"
      AGENT=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('agent','codex'))")
      case "$AGENT" in
        codex) tmux send-keys -t "$SESSION" "cd '$WORKTREE' && touch .orch-setup-done && codex exec $YOLO_FLAG 'Read .task-prompt.md — this is a RETRY. Fix the build error described in the RETRY section. Commit when done.'" C-m ;;
        claude) tmux send-keys -t "$SESSION" "cd '$WORKTREE' && touch .orch-setup-done && claude --dangerously-skip-permissions -p 'Read .task-prompt.md — this is a RETRY. Fix the build error described in the RETRY section. Commit when done.'" C-m ;;
      esac
    fi
    log "gate" "retry_launched" "\"attempt\":$RETRY_COUNT"
    exit 0  # Return to patrol loop
  fi
  
  # No retry — final failure
  log "gate" "fail" "\"reason\":\"$GATE_REASON\",\"retries\":$RETRY_COUNT"
  tmux_kill "$SESSION"
  
  # Cleanup on gate failure
  if [ "$CLEANUP" = "1" ] || [ "$CLEANUP" = "true" ]; then
    if [ "$HOST" = "localhost" ]; then
      cd "$REPO"
      git worktree remove "$WORKTREE" --force 2>/dev/null || true
      git branch -D "$BRANCH" 2>/dev/null || true
    else
      rcmd "cd '$REPO' && git worktree remove '$WORKTREE' --force 2>/dev/null; git branch -D '$BRANCH' 2>/dev/null" || true
    fi
    log "cleanup" "done"
  fi
  
  python3 -c "
import json; s = json.load(open('$STATE_FILE')); s['status'] = 'gate_failed'; s['gate_reason'] = '$GATE_REASON'; s['retry_count'] = $RETRY_COUNT
json.dump(s, open('$STATE_FILE','w'), indent=2)
"
  exit 20
fi

SHORT=$(rcmd "cd '$WORKTREE' && git log -1 --oneline 2>/dev/null" || echo "$COMMIT")
log "gate" "pass" "\"build\":\"$BUILD\",\"commit\":\"$SHORT\""

# ============================================================================
# AI Code Review (optional — set AI_REVIEW=1 to enable)
# ============================================================================
if [ "${AI_REVIEW:-0}" = "1" ]; then
  log "gate" "ai_review" "\"status\":\"starting\""
  DIFF_CONTENT=$(rcmd "cd '$WORKTREE' && git diff '$BASELINE' -- . ':(exclude).task-prompt.md' ':(exclude).task-result.json' ':(exclude)CLAUDE.md' ':(exclude).orch-setup-done' 2>/dev/null | head -500" || echo "")
  if [ -n "$DIFF_CONTENT" ]; then
    echo "$DIFF_CONTENT" > "/tmp/orch-review-${TASK_ID}.diff"
    # Write review prompt
    cat > "/tmp/orch-review-${TASK_ID}.md" << REVIEWEOF
Review this code diff for critical issues ONLY. Ignore style preferences.

Flag as REJECT only if:
- Security vulnerability (SQL injection, XSS, secrets in code)
- Obvious runtime crash (undefined variable, missing import, wrong types)
- Data loss risk

If no critical issues: output exactly "APPROVE"
If critical issues found: output "REJECT: <one-line reason>"

\`\`\`diff
$(cat "/tmp/orch-review-${TASK_ID}.diff")
\`\`\`
REVIEWEOF
    # Use codex for review (lightweight, fast)
    REVIEW_RESULT=$(codex exec --full-auto "$(cat /tmp/orch-review-${TASK_ID}.md)" 2>/dev/null | tail -5 || echo "APPROVE")
    if echo "$REVIEW_RESULT" | grep -qi "REJECT"; then
      log "gate" "ai_review_reject" "\"review\":\"$(echo "$REVIEW_RESULT" | tr '"' "'" | head -3)\""
      # Treat as retryable failure
      GATE_REASON="ai_review_rejected"
      GATE_PASS=0
    else
      log "gate" "ai_review_pass"
    fi
    rm -f "/tmp/orch-review-${TASK_ID}.diff" "/tmp/orch-review-${TASK_ID}.md"
  fi
fi

# ============================================================================
# Pre-merge: remove scaffold files from worktree commit
# ============================================================================
SCAFFOLD_IN_COMMIT=$(rcmd "cd '$WORKTREE' && git diff --name-only '$BASELINE' 2>/dev/null | grep -E '^(\.task-prompt\.md|\.task-result\.json|\.orch-setup-done|CLAUDE\.md)$'" 2>/dev/null || echo "")
if [ -n "$SCAFFOLD_IN_COMMIT" ]; then
  log "gate" "strip_scaffold" "\"files\":\"$(echo "$SCAFFOLD_IN_COMMIT" | tr '\n' ',')\""
  # Remove scaffold files, stage removals, and amend the commit
  rcmd "cd '$WORKTREE' && rm -f .task-prompt.md .task-result.json .orch-setup-done CLAUDE.md 2>/dev/null; git add -A; git commit --amend --no-edit" 2>/dev/null || true
  # Verify removal (best-effort)
  STILL=$(rcmd "cd '$WORKTREE' && git diff --name-only '$BASELINE' | grep -E '^\.task-result\.json$'" 2>/dev/null || echo "")
  if [ -n "$STILL" ]; then
    log "gate" "strip_scaffold_failed" "\"file\":\".task-result.json\""
  fi
fi

# ============================================================================
# Merge
# ============================================================================
if [ "$HOST" = "localhost" ]; then
  cd "$REPO"
  git merge "$BRANCH" --no-edit 2>/dev/null
  DIFF=$(git diff --stat HEAD~1 2>/dev/null || echo "")
else
  rcmd "cd '$REPO' && git merge '$BRANCH' --no-edit" 2>/dev/null
  DIFF=$(rcmd "cd '$REPO' && git diff --stat HEAD~1 2>/dev/null" || echo "")
fi
log "merge" "success" "\"commit\":\"$SHORT\""

# ============================================================================
# Deploy + verify
# ============================================================================
if [ "$DEPLOY" = "1" ] || [ "$DEPLOY" = "true" ]; then
  log "deploy" "starting"
  DEPLOY_RESULT="skipped"
  # Read VERIFY_* env vars from state file if set
  VERIFY_BROWSER=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('verify_browser',''))" 2>/dev/null || echo "")
  VERIFY_MANIFEST=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('verify_manifest',''))" 2>/dev/null || echo "")
  VERIFY_SHOTS_DIR=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('verify_shots_dir',''))" 2>/dev/null || echo "")
  
  if [ -x "$SCRIPTS_DIR/deploy-verify.sh" ]; then
    if [ "$HOST" = "localhost" ]; then
      DEPLOY_RESULT=$(VERIFY_BROWSER="$VERIFY_BROWSER" VERIFY_MANIFEST="$VERIFY_MANIFEST" VERIFY_SHOTS_DIR="$VERIFY_SHOTS_DIR" \
        bash "$SCRIPTS_DIR/deploy-verify.sh" "$REPO" 2>&1 | tail -1 || echo "failed")
    else
      DEPLOY_RESULT=$(rcmd "VERIFY_BROWSER='$VERIFY_BROWSER' VERIFY_MANIFEST='$VERIFY_MANIFEST' bash '$SCRIPTS_DIR/deploy-verify.sh' '$REPO'" 2>&1 | tail -1 || echo "failed")
    fi
  fi
  log "deploy" "$DEPLOY_RESULT"
fi

# ============================================================================
# Cleanup (tmux + worktree + branch)
# ============================================================================
tmux_kill "$SESSION"
if [ "$CLEANUP" = "1" ] || [ "$CLEANUP" = "true" ]; then
  if [ "$HOST" = "localhost" ]; then
    cd "$REPO"
    git worktree remove "$WORKTREE" --force 2>/dev/null || true
    git branch -D "$BRANCH" 2>/dev/null || true
  else
    rcmd "cd '$REPO' && git worktree remove '$WORKTREE' --force 2>/dev/null; git branch -D '$BRANCH' 2>/dev/null" || true
  fi
  log "cleanup" "done"
fi

python3 -c "
import json; s = json.load(open('$STATE_FILE')); s['status'] = 'completed'; s['gate'] = 'passed'
json.dump(s, open('$STATE_FILE','w'), indent=2)
"

log "complete" "success" "\"task\":\"$TASK_ID\""
exit 10
