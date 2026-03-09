#!/usr/bin/env bash
set -euo pipefail

export PATH="$PATH:/run/current-system/sw/bin"

usage() {
  cat >&2 <<'USAGE'
Usage: section-step.sh \
  --section <name> \
  --instruction <text> \
  --repo <path> \
  --base <branch> \
  --plan <path> \
  --current-branch <name> \
  --head-sha <sha> \
  --system-prompt-file <path> \
  --section-timeout <seconds> \
  --total-deadline-epoch <epoch-seconds> \
  [--model <name>]
USAGE
}

SECTION=""
INSTRUCTION=""
REPO_PATH=""
BASE_BRANCH=""
PLAN_PATH=""
CURRENT_BRANCH=""
HEAD_SHA=""
SYSTEM_PROMPT_FILE=""
SECTION_TIMEOUT=""
TOTAL_DEADLINE_EPOCH=""
MODEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --section)
      SECTION="${2:-}"
      shift 2
      ;;
    --instruction)
      INSTRUCTION="${2:-}"
      shift 2
      ;;
    --repo)
      REPO_PATH="${2:-}"
      shift 2
      ;;
    --base)
      BASE_BRANCH="${2:-}"
      shift 2
      ;;
    --plan)
      PLAN_PATH="${2:-}"
      shift 2
      ;;
    --current-branch)
      CURRENT_BRANCH="${2:-}"
      shift 2
      ;;
    --head-sha)
      HEAD_SHA="${2:-}"
      shift 2
      ;;
    --system-prompt-file)
      SYSTEM_PROMPT_FILE="${2:-}"
      shift 2
      ;;
    --section-timeout)
      SECTION_TIMEOUT="${2:-}"
      shift 2
      ;;
    --total-deadline-epoch)
      TOTAL_DEADLINE_EPOCH="${2:-}"
      shift 2
      ;;
    --model)
      MODEL="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$SECTION" || -z "$INSTRUCTION" || -z "$REPO_PATH" || -z "$BASE_BRANCH" || -z "$PLAN_PATH" || -z "$CURRENT_BRANCH" || -z "$HEAD_SHA" || -z "$SYSTEM_PROMPT_FILE" || -z "$SECTION_TIMEOUT" || -z "$TOTAL_DEADLINE_EPOCH" ]]; then
  echo "Error: missing required arguments" >&2
  usage
  exit 1
fi

if [[ ! "$SECTION_TIMEOUT" =~ ^[0-9]+$ ]] || (( SECTION_TIMEOUT <= 0 )); then
  echo "Error: --section-timeout must be a positive integer" >&2
  exit 1
fi
if [[ ! "$TOTAL_DEADLINE_EPOCH" =~ ^[0-9]+$ ]] || (( TOTAL_DEADLINE_EPOCH <= 0 )); then
  echo "Error: --total-deadline-epoch must be a positive integer" >&2
  exit 1
fi

if [[ ! -f "$SYSTEM_PROMPT_FILE" ]]; then
  echo "Error: system prompt file not found: $SYSTEM_PROMPT_FILE" >&2
  exit 1
fi
if [[ ! -f "$PLAN_PATH" ]]; then
  echo "Error: plan file not found: $PLAN_PATH" >&2
  exit 1
fi

now_epoch="$(date +%s)"
remaining=$((TOTAL_DEADLINE_EPOCH - now_epoch))
if (( remaining <= 0 )); then
  echo "Error: live review exceeded total timeout budget before section '$SECTION'." >&2
  exit 1
fi

effective_timeout="$SECTION_TIMEOUT"
if (( remaining < SECTION_TIMEOUT )); then
  effective_timeout="$remaining"
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
SYSTEM_PROMPT="$TMP_DIR/system_prompt.txt"

{
  cat "$SYSTEM_PROMPT_FILE"
  cat <<EOF2

TASK CONTEXT:
- Repository: $REPO_PATH
- Base branch: $BASE_BRANCH
- Current branch: $CURRENT_BRANCH
- Head SHA: $HEAD_SHA
- Plan file: $PLAN_PATH

REVIEW MODE: live
LIVE REVIEW SECTION: $SECTION
- This is one checkpoint in a multi-step interactive review.
- Review only the named section and do not continue to other sections.
- Keep decisions explicit and label options so user can select quickly.

SECTION-SPECIFIC INSTRUCTIONS:
$INSTRUCTION

SHARED PLAN CONTEXT:
PLAN CONTEXT (shared across sections):
- Plan path: $PLAN_PATH
- Base branch: $BASE_BRANCH
- Current branch: $CURRENT_BRANCH
- Head SHA: $HEAD_SHA

Plan headings:
$(grep -E '^## ' "$PLAN_PATH" || true)

Plan excerpt (first 160 lines):
$(sed -n '1,160p' "$PLAN_PATH")
EOF2
} > "$SYSTEM_PROMPT"

if ! command -v codex >/dev/null 2>&1; then
  echo "Error: codex command not found" >&2
  exit 1
fi
if ! command -v timeout >/dev/null 2>&1; then
  echo "Error: timeout command is required for live mode." >&2
  exit 1
fi

CODEx_CMD=(codex exec --sandbox read-only --ephemeral)
if [[ -n "$MODEL" ]]; then
  CODEx_CMD+=(--model "$MODEL")
fi
CODEx_CMD+=(-- "$(cat "$SYSTEM_PROMPT")")

section_output="$({
  cd "$REPO_PATH"
  timeout -k5s "${effective_timeout}s" "${CODEx_CMD[@]}"
})"

preview="## $SECTION

$section_output"
prompt="[$SECTION] Review checkpoint complete. Approve to continue to the next section."

python3 - "$prompt" "$preview" <<'PY'
import json
import sys

prompt = sys.argv[1]
preview = sys.argv[2]
payload = {
    "prompt": prompt,
    "preview": preview,
    "items": []
}
print(json.dumps(payload))
PY
