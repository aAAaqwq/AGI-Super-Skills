#!/usr/bin/env bash
# smoke-wrappers.sh - lightweight behavior checks for wrapper scripts
set -euo pipefail

# Ensure standard tools are available on NixOS
export PATH="$PATH:/run/current-system/sw/bin"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

fake_bin="$tmp_dir/bin"
mkdir -p "$fake_bin"

cat >"$fake_bin/timeout" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 2 ]]; then
  exit 2
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    -k|--kill-after)
      shift 2
      ;;
    -k*)
      shift
      ;;
    -*)
      shift
      ;;
    --*)
      shift
      ;;
    *)
      shift
      break
      ;;
  esac
done

if [[ $# -lt 1 ]]; then
  exit 2
fi

exec "$@"
EOF

cat >"$fake_bin/codex" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
: "${SMOKE_CODEX_ARGS_FILE:?}"
{
  printf -- '---CALL---\n'
  for arg in "$@"; do
    printf '%s\n' "$arg"
  done
} >>"$SMOKE_CODEX_ARGS_FILE"

all_args="$*"

if [[ "$all_args" == *"LIVE REVIEW SECTION:"* ]]; then
  section="$(printf '%s\n' "$all_args" | sed -nE 's/.*LIVE REVIEW SECTION: ([A-Za-z ]+).*/\1/p' | head -n 1)"
  if [[ -z "$section" ]]; then
    section="Unknown"
  fi
  cat <<EOF2
# ${section} Findings

1. ${section} issue.
A) Do recommended ${section} option.
B) Do alternate ${section} option.
EOF2
  exit 0
fi

cat <<'PLAN'
# Plan: Smoke test

## Fast-Path
- Eligible: yes
- Reason: test

## 1. Problem statement
x

## 2. Current state evidence
- Files:
  - `README.md#L1-L1` — test
- Commands run:
  - `rg foo`
- Observations:
  - test

## 3. Proposed approach
x

## 4. Step-by-step change list
1. a
2. b

## 5. Risks + rollback
- Risks:
  - r
- Rollback:
  - `git restore .`

## 6. Test plan
- Automated:
  - `echo ok`
- Manual:
  - check
- Success criteria:
  - ok

## 7. Out-of-scope
- none

## 8. Approval prompt
Reply with one:
- `APPROVE: smoke`
- `REVISE: tweak`
PLAN
exit 0
EOF

cat >"$fake_bin/claude" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
: "${SMOKE_CLAUDE_ARGS_FILE:?}"
{
  for arg in "$@"; do
    printf '%s\n' "$arg"
  done
} >"$SMOKE_CLAUDE_ARGS_FILE"
exit 0
EOF

cat >"$fake_bin/acpx" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${SMOKE_ACPX_ARGS_FILE:-}" ]]; then
  {
    printf -- '---CALL---\n'
    for arg in "$@"; do
      printf '%s\n' "$arg"
    done
  } >>"$SMOKE_ACPX_ARGS_FILE"
fi

case "${SMOKE_ACPX_BEHAVIOR:-fail}" in
  success)
    printf 'acpx ok\n'
    exit 0
    ;;
  fail)
    printf 'acpx fail\n' >&2
    exit 1
    ;;
  *)
    printf 'invalid SMOKE_ACPX_BEHAVIOR\n' >&2
    exit 2
    ;;
esac
EOF

cat >"$fake_bin/tmux" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "mock tmux unavailable" >&2
exit 1
EOF

cat >"$fake_bin/lobster" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

state_file="${SMOKE_LOBSTER_STATE_FILE:-}"
if [[ -z "$state_file" ]]; then
  state_file="$(mktemp)"
fi

mode=""
cmd=""
token=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    run|resume)
      cmd="$1"
      shift
      ;;
    --mode)
      mode="${2:-}"
      shift 2
      ;;
    --token)
      token="${2:-}"
      shift 2
      ;;
    --file|--args-json|--approve)
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

if [[ "${SMOKE_LOBSTER_BEHAVIOR:-ok}" == "fail" ]]; then
  echo "lobster fail" >&2
  exit 1
fi

if [[ "$mode" != "tool" ]]; then
  echo "unsupported mode" >&2
  exit 2
fi

read_state() {
  if [[ -f "$state_file" ]]; then
    cat "$state_file"
  else
    echo "0"
  fi
}

write_state() {
  printf '%s' "$1" > "$state_file"
}

emit_approval() {
  local section="$1"
  local idx="$2"
  cat <<JSON
{
  "protocolVersion": 1,
  "ok": true,
  "status": "needs_approval",
  "output": [],
  "requiresApproval": {
    "type": "approval_request",
    "prompt": "[$section] Review checkpoint complete. Approve to continue to the next section.",
    "items": [],
    "preview": "## $section\n\n# $section Findings\n\n1. $section issue.\nA) Do recommended $section option.\nB) Do alternate $section option.",
    "resumeToken": "token-$idx"
  }
}
JSON
}

if [[ "$cmd" == "run" ]]; then
  write_state "1"
  emit_approval "Architecture" "1"
  exit 0
fi

if [[ "$cmd" == "resume" ]]; then
  case "$(read_state)" in
    1)
      write_state "2"
      emit_approval "Code Quality" "2"
      ;;
    2)
      write_state "3"
      emit_approval "Tests" "3"
      ;;
    3)
      write_state "4"
      emit_approval "Performance" "4"
      ;;
    *)
      write_state "5"
      cat <<'JSON'
{
  "protocolVersion": 1,
  "ok": true,
  "status": "ok",
  "output": [
    {
      "status": "ok"
    }
  ],
  "requiresApproval": null
}
JSON
      ;;
  esac
  exit 0
fi

echo "unsupported command" >&2
exit 2
EOF

chmod +x "$fake_bin/timeout" "$fake_bin/codex" "$fake_bin/claude" "$fake_bin/acpx" "$fake_bin/tmux" "$fake_bin/lobster"

assert_contains() {
  local file="$1"
  local expected="$2"
  if ! grep -Fq -- "$expected" "$file"; then
    printf 'Assertion failed: expected "%s" in %s\n' "$expected" "$file" >&2
    printf '--- file content ---\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_not_contains() {
  local file="$1"
  local unexpected="$2"
  if grep -Fq -- "$unexpected" "$file"; then
    printf 'Assertion failed: did not expect "%s" in %s\n' "$unexpected" "$file" >&2
    printf '%s\n' '--- file content ---' >&2
    cat "$file" >&2
    exit 1
  fi
}

test_invalid_mode_rejected() {
  local output="$tmp_dir/invalid-mode.txt"
  if "$SCRIPT_DIR/safe-fallback.sh" bad-mode "prompt" >"$output" 2>&1; then
    printf 'Expected safe-fallback.sh to reject invalid mode\n' >&2
    exit 1
  fi
  assert_contains "$output" "invalid mode"
}

test_invalid_cli_rejected() {
  local output="$tmp_dir/invalid-cli.txt"
  if "$SCRIPT_DIR/safe-review.sh" bad-cli >"$output" 2>&1; then
    printf 'Expected safe-review.sh to reject invalid CLI\n' >&2
    exit 1
  fi
  assert_contains "$output" "Unknown CLI"
}

test_review_prompt_pass_through() {
  local prompt="Review this PR thoroughly: preserve this custom prompt text and include edge-case notes for wrappers 1234567890."
  local title="${prompt:0:100}"
  local codex_args="$tmp_dir/codex-args.txt"
  local output="$tmp_dir/review-pass-through.txt"

  PATH="$fake_bin:$PATH" \
  SMOKE_CODEX_ARGS_FILE="$codex_args" \
  "$SCRIPT_DIR/safe-fallback.sh" review "$prompt" >"$output" 2>&1

  assert_contains "$codex_args" "review"
  assert_contains "$codex_args" "--title"
  assert_contains "$codex_args" "$title"
  assert_contains "$codex_args" "$prompt"
}

test_invalid_impl_mode_rejected() {
  local output="$tmp_dir/invalid-impl-mode.txt"
  if CODING_AGENT_IMPL_MODE=invalid "$SCRIPT_DIR/safe-fallback.sh" impl "prompt" >"$output" 2>&1; then
    printf 'Expected safe-fallback.sh to reject invalid CODING_AGENT_IMPL_MODE\n' >&2
    exit 1
  fi
  assert_contains "$output" "Invalid CODING_AGENT_IMPL_MODE"
}

test_impl_direct_mode_uses_codex_exec() {
  local prompt="Implement feature with direct mode fallback check."
  local codex_args="$tmp_dir/codex-impl-args.txt"
  local output="$tmp_dir/impl-direct.txt"

  PATH="$fake_bin:$PATH" \
  CODING_AGENT_IMPL_MODE=direct \
  SMOKE_CODEX_ARGS_FILE="$codex_args" \
  "$SCRIPT_DIR/safe-fallback.sh" impl "$prompt" >"$output" 2>&1

  assert_contains "$codex_args" "--yolo"
  assert_contains "$codex_args" "exec"
  assert_contains "$codex_args" "$prompt"
}

test_impl_uses_acpx_first_when_available() {
  local prompt="Implement feature via acpx first."
  local acpx_args="$tmp_dir/acpx-impl-args.txt"
  local codex_args="$tmp_dir/codex-impl-no-call.txt"
  local output="$tmp_dir/impl-acpx-first.txt"

  PATH="$fake_bin:$PATH" \
  CODING_AGENT_IMPL_MODE=direct \
  SMOKE_ACPX_BEHAVIOR=success \
  SMOKE_ACPX_ARGS_FILE="$acpx_args" \
  SMOKE_CODEX_ARGS_FILE="$codex_args" \
  "$SCRIPT_DIR/safe-fallback.sh" impl "$prompt" >"$output" 2>&1

  assert_contains "$acpx_args" "codex"
  assert_contains "$acpx_args" "exec"
  assert_contains "$acpx_args" "--cwd"
  assert_contains "$acpx_args" "--format"
  assert_contains "$acpx_args" "quiet"
  if [[ -f "$codex_args" ]]; then
    assert_not_contains "$codex_args" "---CALL---"
  fi
}

test_review_uses_codex_review_first() {
  local prompt="Review this PR via codex review first."
  local acpx_args="$tmp_dir/acpx-review-no-call.txt"
  local codex_args="$tmp_dir/codex-review-first-args.txt"
  local output="$tmp_dir/review-codex-first.txt"

  PATH="$fake_bin:$PATH" \
  SMOKE_ACPX_BEHAVIOR=success \
  SMOKE_ACPX_ARGS_FILE="$acpx_args" \
  SMOKE_CODEX_ARGS_FILE="$codex_args" \
  "$SCRIPT_DIR/safe-fallback.sh" review "$prompt" >"$output" 2>&1

  assert_contains "$codex_args" "review"
  assert_contains "$codex_args" "--base"
  assert_contains "$codex_args" "$prompt"
  if [[ -f "$acpx_args" ]]; then
    assert_not_contains "$acpx_args" "---CALL---"
  fi
}

test_invalid_acp_enable_rejected() {
  local output="$tmp_dir/invalid-acp-enable.txt"
  if CODING_AGENT_ACP_ENABLE=2 "$SCRIPT_DIR/safe-fallback.sh" impl "prompt" >"$output" 2>&1; then
    printf 'Expected safe-fallback.sh to reject invalid CODING_AGENT_ACP_ENABLE\n' >&2
    exit 1
  fi
  assert_contains "$output" "CODING_AGENT_ACP_ENABLE must be 0 or 1"
}

test_acp_agent_alias_forwarded() {
  local prompt="Use ACP alias forwarding."
  local acpx_args="$tmp_dir/acpx-alias-args.txt"
  local output="$tmp_dir/acpx-alias.txt"

  PATH="$fake_bin:$PATH" \
  CODING_AGENT_ACP_AGENT=gemini \
  SMOKE_ACPX_BEHAVIOR=success \
  SMOKE_ACPX_ARGS_FILE="$acpx_args" \
  "$SCRIPT_DIR/safe-fallback.sh" impl "$prompt" >"$output" 2>&1

  assert_contains "$acpx_args" "gemini"
  assert_contains "$acpx_args" "exec"
  assert_contains "$acpx_args" "$prompt"
}

test_acpx_cmd_override_is_used() {
  local custom_acpx="$tmp_dir/custom-acpx"
  local acpx_args="$tmp_dir/acpx-override-args.txt"
  local output="$tmp_dir/acpx-override.txt"
  local prompt="Use overridden acpx binary."

  cat >"$custom_acpx" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
: "${SMOKE_ACPX_ARGS_FILE:?}"
{
  printf -- '---OVERRIDE---\n'
  for arg in "$@"; do
    printf '%s\n' "$arg"
  done
} >>"$SMOKE_ACPX_ARGS_FILE"
exit 0
EOF
  chmod +x "$custom_acpx"

  PATH="$fake_bin:$PATH" \
  CODING_AGENT_ACPX_CMD="$custom_acpx" \
  SMOKE_ACPX_ARGS_FILE="$acpx_args" \
  "$SCRIPT_DIR/safe-fallback.sh" impl "$prompt" >"$output" 2>&1

  assert_contains "$acpx_args" "---OVERRIDE---"
  assert_contains "$acpx_args" "$prompt"
}

test_acp_disable_skips_acpx() {
  local prompt="Skip acpx when disabled."
  local acpx_args="$tmp_dir/acpx-disabled-args.txt"
  local codex_args="$tmp_dir/codex-disabled-args.txt"
  local output="$tmp_dir/acpx-disabled.txt"

  PATH="$fake_bin:$PATH" \
  CODING_AGENT_ACP_ENABLE=0 \
  SMOKE_ACPX_BEHAVIOR=success \
  SMOKE_ACPX_ARGS_FILE="$acpx_args" \
  SMOKE_CODEX_ARGS_FILE="$codex_args" \
  "$SCRIPT_DIR/safe-fallback.sh" impl "$prompt" >"$output" 2>&1

  if [[ -f "$acpx_args" ]]; then
    assert_not_contains "$acpx_args" "---CALL---"
  fi
  assert_contains "$codex_args" "exec"
  assert_contains "$codex_args" "$prompt"
}

test_code_plan_generates_artifact() {
  local repo="$tmp_dir/repo"
  local codex_args="$tmp_dir/codex-plan-args.txt"
  mkdir -p "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  PATH="$fake_bin:$PATH" \
  SMOKE_CODEX_ARGS_FILE="$codex_args" \
  "$SCRIPT_DIR/code-plan" --engine codex --repo "$repo" --base main "smoke plan request" > "$tmp_dir/code-plan.out" 2>&1

  local plan_file
  plan_file="$(find "$repo/.ai/plans" -maxdepth 1 -type f -name '*.md' | head -1)"
  [[ -n "$plan_file" && -f "$plan_file" ]] || { echo "Expected plan file" >&2; exit 1; }
  assert_contains "$codex_args" "--sandbox"
  assert_contains "$codex_args" "read-only"
  assert_contains "$codex_args" "--ephemeral"
  assert_contains "$tmp_dir/code-plan.out" "RUN_EVENT start"
  assert_contains "$tmp_dir/code-plan.out" "RUN_EVENT done"
  assert_contains "$plan_file" "status: PENDING"
  assert_contains "$plan_file" "## 8. Approval prompt"
}

test_safe_impl_claude_plan_mode_no_dangerous_skip() {
  local repo="$tmp_dir/repo-claude"
  local claude_args="$tmp_dir/claude-args.txt"
  mkdir -p "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"
  git -C "$repo" checkout -q -b feat/test

  (
    cd "$repo"
    PATH="$fake_bin:$PATH" \
    SMOKE_CLAUDE_ARGS_FILE="$claude_args" \
    TIMEOUT=10 \
    "$SCRIPT_DIR/safe-impl.sh" claude -p --permission-mode plan "plan only"
  ) > "$tmp_dir/safe-impl-claude.out" 2>&1

  if grep -Fq -- "--dangerously-skip-permissions" "$claude_args"; then
    echo "Expected no dangerous-skip flag in plan permission mode" >&2
    exit 1
  fi
}

test_plan_review_generates_artifact() {
  local repo="$tmp_dir/repo-plan-review"
  local codex_args="$tmp_dir/codex-plan-review-args.txt"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  cat > "$repo/.ai/plans/2026-02-19-000001-old.md" <<'EOF'
---
id: 2026-02-19-000001-old
status: PENDING
---

# Plan: Old
EOF

  cat > "$repo/.ai/plans/2026-02-19-000002-new.md" <<'EOF'
---
id: 2026-02-19-000002-new
status: PENDING
---

# Plan: New
EOF

  # Simulate old plan being modified later; selector should still pick latest generated filename.
  touch "$repo/.ai/plans/2026-02-19-000001-old.md"

  PATH="$fake_bin:$PATH" \
  SMOKE_CODEX_ARGS_FILE="$codex_args" \
  "$SCRIPT_DIR/plan-review" --repo "$repo" > "$tmp_dir/plan-review.out" 2>&1

  local review_file
  review_file="$(find "$repo/.ai/plan-reviews" -maxdepth 1 -type f -name '*.md' | head -1)"
  [[ -n "$review_file" && -f "$review_file" ]] || { echo "Expected plan review artifact" >&2; exit 1; }
  local latest_metadata="$repo/.ai/plan-reviews/latest-2026-02-19-000002-new.json"
  [[ -f "$latest_metadata" ]] || { echo "Expected latest metadata file" >&2; exit 1; }
  local history_metadata
  history_metadata="$(find "$repo/.ai/plan-reviews" -maxdepth 1 -type f -name '*.json' ! -name 'latest-*' | head -1)"
  [[ -n "$history_metadata" && -f "$history_metadata" ]] || { echo "Expected metadata history file" >&2; exit 1; }
  assert_contains "$codex_args" "exec"
  assert_contains "$codex_args" "--sandbox"
  assert_contains "$codex_args" "read-only"
  assert_contains "$codex_args" "--ephemeral"
  assert_contains "$tmp_dir/plan-review.out" "RUN_EVENT start"
  assert_contains "$tmp_dir/plan-review.out" "RUN_EVENT done"
  assert_contains "$codex_args" "Plan file: $repo/.ai/plans/2026-02-19-000002-new.md"
  assert_contains "$codex_args" "REVIEW MODE: batch"
  assert_contains "$latest_metadata" "\"ready_for_implementation\": false"
  assert_contains "$latest_metadata" "\"blocking_decisions\": [\"Run ./scripts/plan-review-live to resolve interactive decisions\"]"
}

test_plan_review_output_parent_dirs_created() {
  local repo="$tmp_dir/repo-plan-review-output"
  local codex_args="$tmp_dir/codex-plan-review-output-args.txt"
  local output_path="$repo/reports/plan/review.md"

  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  cat > "$repo/.ai/plans/2026-02-19-000003-smoke.md" <<'EOF'
---
id: 2026-02-19-000003-smoke
status: PENDING
---

# Plan: Smoke
EOF

  PATH="$fake_bin:$PATH" \
  SMOKE_CODEX_ARGS_FILE="$codex_args" \
  "$SCRIPT_DIR/plan-review" --repo "$repo" --output "$output_path" > "$tmp_dir/plan-review-output.out"

  [[ -f "$output_path" ]] || { echo "Expected nested output artifact" >&2; exit 1; }
}

test_plan_review_live_lobster_default_engine() {
  local repo="$tmp_dir/repo-plan-review-live-lobster-default"
  local output_file="$repo/.ai/plan-reviews/live-output.md"
  local lobster_state="$tmp_dir/lobster-state.txt"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  cat > "$repo/.ai/plans/2026-02-19-000004a-live.md" <<'EOF'
---
id: 2026-02-19-000004a-live
status: APPROVED
---

# Plan: Live Lobster
EOF

  printf '1A\nnone\n2A\nnone\n3A\nnone\n4A\nnone\n' | \
    PATH="$fake_bin:$PATH" \
    PLAN_REVIEW_LIVE_ALLOW_NON_TTY=1 \
    SMOKE_LOBSTER_STATE_FILE="$lobster_state" \
    "$SCRIPT_DIR/plan-review-live" --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000004a-live.md" --output "$output_file" > "$tmp_dir/plan-review-live-lobster-default.out"

  [[ -f "$output_file" ]] || { echo "Expected live review markdown output (lobster)" >&2; exit 1; }
  assert_contains "$output_file" "## Architecture"
  assert_contains "$output_file" "## Code Quality"
  assert_contains "$output_file" "## Tests"
  assert_contains "$output_file" "## Performance"

  local latest_metadata="$repo/.ai/plan-reviews/latest-2026-02-19-000004a-live.json"
  [[ -f "$latest_metadata" ]] || { echo "Expected lobster live latest metadata file" >&2; exit 1; }
  assert_contains "$latest_metadata" "\"mode\": \"live\""
  assert_contains "$latest_metadata" "\"ready_for_implementation\": true"
  assert_contains "$latest_metadata" "\"blocking_decisions\": []"
  assert_contains "$latest_metadata" "\"resolved_decisions\": [\"1A\", \"2A\", \"3A\", \"4A\"]"
}

test_plan_review_live_lobster_resume_preserves_decisions() {
  local repo="$tmp_dir/repo-plan-review-live-lobster-resume"
  local output_file="$repo/.ai/plan-reviews/live-output.md"
  local lobster_state="$tmp_dir/lobster-state-resume.txt"
  local session_state
  session_state="${output_file}.lobster-session.json"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  cat > "$repo/.ai/plans/2026-02-19-000004b-live.md" <<'EOF'
---
id: 2026-02-19-000004b-live
status: APPROVED
---

# Plan: Live Lobster Resume
EOF

  # First run intentionally stops after one section to leave resumable state.
  set +e
  printf '1A\nnone\n' | \
    PATH="$fake_bin:$PATH" \
    PLAN_REVIEW_LIVE_ALLOW_NON_TTY=1 \
    SMOKE_LOBSTER_STATE_FILE="$lobster_state" \
    "$SCRIPT_DIR/plan-review-live" --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000004b-live.md" --output "$output_file" > "$tmp_dir/plan-review-live-lobster-resume-step1.out" 2>&1
  step1_rc=$?
  set -e
  if [[ "$step1_rc" -eq 0 ]]; then
    echo "Expected first lobster run to stop early due missing stdin decisions" >&2
    exit 1
  fi
  [[ -f "$session_state" ]] || { echo "Expected lobster session state file" >&2; exit 1; }
  assert_contains "$session_state" "\"resolved_decisions\": [\"1A\"]"

  # Resume from second section and ensure first decision persists to final metadata.
  printf '2A\nnone\n3A\nnone\n4A\nnone\n' | \
    PATH="$fake_bin:$PATH" \
    PLAN_REVIEW_LIVE_ALLOW_NON_TTY=1 \
    SMOKE_LOBSTER_STATE_FILE="$lobster_state" \
    "$SCRIPT_DIR/plan-review-live" --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000004b-live.md" --output "$output_file" --resume-token "token-2" > "$tmp_dir/plan-review-live-lobster-resume-step2.out"

  local latest_metadata="$repo/.ai/plan-reviews/latest-2026-02-19-000004b-live.json"
  [[ -f "$latest_metadata" ]] || { echo "Expected lobster resume latest metadata file" >&2; exit 1; }
  assert_contains "$latest_metadata" "\"ready_for_implementation\": true"
  assert_contains "$latest_metadata" "\"resolved_decisions\": [\"1A\", \"2A\", \"3A\", \"4A\"]"
  [[ ! -f "$session_state" ]] || { echo "Expected session state file to be cleared after completion" >&2; exit 1; }
}

test_plan_review_live_generates_ready_metadata() {
  local repo="$tmp_dir/repo-plan-review-live"
  local codex_args="$tmp_dir/codex-plan-review-live-args.txt"
  local output_file="$repo/.ai/plan-reviews/live-output.md"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  cat > "$repo/.ai/plans/2026-02-19-000004-live.md" <<'EOF'
---
id: 2026-02-19-000004-live
status: APPROVED
---

# Plan: Live
EOF

  printf '1A\nnone\n2A\nnone\n3A\nnone\n4A\nnone\n' | \
    PATH="$fake_bin:$PATH" \
    SMOKE_CODEX_ARGS_FILE="$codex_args" \
    PLAN_REVIEW_LIVE_ALLOW_NON_TTY=1 \
    "$SCRIPT_DIR/plan-review-live" --engine legacy --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000004-live.md" --output "$output_file" > "$tmp_dir/plan-review-live.out"

  [[ -f "$output_file" ]] || { echo "Expected live review markdown output" >&2; exit 1; }
  assert_contains "$output_file" "## Architecture"
  assert_contains "$output_file" "## Code Quality"
  assert_contains "$output_file" "## Tests"
  assert_contains "$output_file" "## Performance"

  local latest_metadata="$repo/.ai/plan-reviews/latest-2026-02-19-000004-live.json"
  [[ -f "$latest_metadata" ]] || { echo "Expected live latest metadata file" >&2; exit 1; }
  assert_contains "$latest_metadata" "\"mode\": \"live\""
  assert_contains "$latest_metadata" "\"ready_for_implementation\": true"
  assert_contains "$latest_metadata" "\"blocking_decisions\": []"
  assert_contains "$latest_metadata" "\"resolved_decisions\": [\"1A\", \"2A\", \"3A\", \"4A\"]"

  assert_contains "$codex_args" "REVIEW MODE: live"
  assert_contains "$codex_args" "LIVE REVIEW SECTION: Architecture"
  assert_contains "$codex_args" "LIVE REVIEW SECTION: Code Quality"
  assert_contains "$codex_args" "LIVE REVIEW SECTION: Tests"
  assert_contains "$codex_args" "LIVE REVIEW SECTION: Performance"
}

test_plan_review_live_non_tty_auto_apply_with_flags() {
  local repo="$tmp_dir/repo-plan-review-live-auto-flags"
  local output_file="$repo/.ai/plan-reviews/live-auto-flags.md"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  cat > "$repo/.ai/plans/2026-02-19-000005-live-auto.md" <<'EOF'
---
id: 2026-02-19-000005-live-auto
status: APPROVED
---

# Plan: Live Auto
EOF

  PATH="$fake_bin:$PATH" \
    "$SCRIPT_DIR/plan-review-live" --engine legacy --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000005-live-auto.md" --decisions "1A,2A,3A,4A" --blocking none --output "$output_file" > "$tmp_dir/plan-review-live-auto-flags.out"

  [[ -f "$output_file" ]] || { echo "Expected non-tty auto-apply output markdown" >&2; exit 1; }
  assert_contains "$output_file" "Mode: live (non-tty auto-apply)"

  local latest_metadata="$repo/.ai/plan-reviews/latest-2026-02-19-000005-live-auto.json"
  [[ -f "$latest_metadata" ]] || { echo "Expected latest metadata for non-tty auto-apply" >&2; exit 1; }
  assert_contains "$latest_metadata" "\"ready_for_implementation\": true"
  assert_contains "$latest_metadata" "\"blocking_decisions\": []"
  assert_contains "$latest_metadata" "\"resolved_decisions\": [\"1A\", \"2A\", \"3A\", \"4A\"]"
}

test_plan_review_live_resolution_inputs_override_allow_non_tty() {
  local repo="$tmp_dir/repo-plan-review-live-allow-priority"
  local output_file="$repo/.ai/plan-reviews/live-allow-priority.md"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  cat > "$repo/.ai/plans/2026-02-19-000005b-live-auto.md" <<'EOF'
---
id: 2026-02-19-000005b-live-auto
status: APPROVED
---

# Plan: Live Auto Allow Priority
EOF

  # Do not pass SMOKE_CODEX_ARGS_FILE on purpose: if interactive flow runs, fake codex will fail.
  PATH="$fake_bin:$PATH" \
    PLAN_REVIEW_LIVE_ALLOW_NON_TTY=1 \
    "$SCRIPT_DIR/plan-review-live" --engine legacy --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000005b-live-auto.md" --decisions "1A,2A,3A,4A" --blocking none --output "$output_file" > "$tmp_dir/plan-review-live-allow-priority.out"

  [[ -f "$output_file" ]] || { echo "Expected auto-apply output with ALLOW_NON_TTY set" >&2; exit 1; }
  assert_contains "$output_file" "Mode: live (non-tty auto-apply)"
  local latest_metadata="$repo/.ai/plan-reviews/latest-2026-02-19-000005b-live-auto.json"
  [[ -f "$latest_metadata" ]] || { echo "Expected latest metadata for allow-priority test" >&2; exit 1; }
  assert_contains "$latest_metadata" "\"ready_for_implementation\": true"
}

test_plan_review_live_non_tty_auto_apply_with_resolve_file() {
  local repo="$tmp_dir/repo-plan-review-live-auto-file"
  local output_file="$repo/.ai/plan-reviews/live-auto-file.md"
  local resolve_file="$tmp_dir/resolve-file.json"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  cat > "$repo/.ai/plans/2026-02-19-000006-live-auto.md" <<'EOF'
---
id: 2026-02-19-000006-live-auto
status: APPROVED
---

# Plan: Live Auto File
EOF

  cat > "$resolve_file" <<'EOF'
{
  "resolved_decisions": ["1A", "1A", "none", "2A", "3A", "4A"],
  "blocking_decisions": ["none"]
}
EOF

  PATH="$fake_bin:$PATH" \
    "$SCRIPT_DIR/plan-review-live" --engine legacy --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000006-live-auto.md" --resolve-file "$resolve_file" --output "$output_file" > "$tmp_dir/plan-review-live-auto-file.out"

  [[ -f "$output_file" ]] || { echo "Expected non-tty auto-apply output markdown (resolve file)" >&2; exit 1; }
  assert_contains "$output_file" "Mode: live (non-tty auto-apply)"

  local latest_metadata="$repo/.ai/plan-reviews/latest-2026-02-19-000006-live-auto.json"
  [[ -f "$latest_metadata" ]] || { echo "Expected latest metadata for resolve-file auto-apply" >&2; exit 1; }
  assert_contains "$latest_metadata" "\"ready_for_implementation\": true"
  assert_contains "$latest_metadata" "\"blocking_decisions\": []"
  assert_contains "$latest_metadata" "\"resolved_decisions\": [\"1A\", \"2A\", \"3A\", \"4A\"]"
}

test_plan_review_live_rejects_mixed_resolution_inputs() {
  local repo="$tmp_dir/repo-plan-review-live-mixed-inputs"
  local resolve_file="$tmp_dir/resolve-mixed-inputs.json"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  cat > "$repo/.ai/plans/2026-02-19-000009-live-mixed.md" <<'EOF'
---
id: 2026-02-19-000009-live-mixed
status: APPROVED
---

# Plan: Live Mixed
EOF

  cat > "$resolve_file" <<'EOF'
{
  "resolved_decisions": ["1A"],
  "blocking_decisions": []
}
EOF

  local output="$tmp_dir/plan-review-live-mixed-inputs.out"
  if PATH="$fake_bin:$PATH" "$SCRIPT_DIR/plan-review-live" --engine legacy --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000009-live-mixed.md" --resolve-file "$resolve_file" --decisions "2B" > "$output" 2>&1; then
    echo "Expected mixed resolution inputs to fail" >&2
    exit 1
  fi
  assert_contains "$output" "--resolve-file cannot be combined"
}

test_plan_review_live_non_tty_requires_resolution_inputs() {
  local repo="$tmp_dir/repo-plan-review-live-no-inputs"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  cat > "$repo/.ai/plans/2026-02-19-000007-live-no-input.md" <<'EOF'
---
id: 2026-02-19-000007-live-no-input
status: APPROVED
---

# Plan: Live No Inputs
EOF

  local output="$tmp_dir/plan-review-live-no-inputs.out"
  if PATH="$fake_bin:$PATH" "$SCRIPT_DIR/plan-review-live" --engine legacy --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000007-live-no-input.md" > "$output" 2>&1; then
    echo "Expected plan-review-live to fail in non-tty mode without decision inputs" >&2
    exit 1
  fi
  assert_contains "$output" "non-TTY live mode requires decision input"
  assert_contains "$output" "--resolve-file"
}

test_plan_review_live_rejects_invalid_resolve_file() {
  local repo="$tmp_dir/repo-plan-review-live-invalid-resolve"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  cat > "$repo/.ai/plans/2026-02-19-000008-live-invalid.md" <<'EOF'
---
id: 2026-02-19-000008-live-invalid
status: APPROVED
---

# Plan: Live Invalid
EOF

  local invalid_json="$tmp_dir/resolve-invalid-json.json"
  local missing_key="$tmp_dir/resolve-missing-key.json"
  local wrong_type="$tmp_dir/resolve-wrong-type.json"

  printf '{' > "$invalid_json"
  cat > "$missing_key" <<'EOF'
{"resolved_decisions": ["1A"]}
EOF
  cat > "$wrong_type" <<'EOF'
{
  "resolved_decisions": ["1A", 2],
  "blocking_decisions": []
}
EOF

  local output_json="$tmp_dir/plan-review-live-invalid-json.out"
  if PATH="$fake_bin:$PATH" "$SCRIPT_DIR/plan-review-live" --engine legacy --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000008-live-invalid.md" --resolve-file "$invalid_json" > "$output_json" 2>&1; then
    echo "Expected invalid JSON resolve-file to fail" >&2
    exit 1
  fi
  assert_contains "$output_json" "invalid resolve file JSON"

  local output_missing="$tmp_dir/plan-review-live-missing-key.out"
  if PATH="$fake_bin:$PATH" "$SCRIPT_DIR/plan-review-live" --engine legacy --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000008-live-invalid.md" --resolve-file "$missing_key" > "$output_missing" 2>&1; then
    echo "Expected missing-key resolve-file to fail" >&2
    exit 1
  fi
  assert_contains "$output_missing" "missing required key 'blocking_decisions'"

  local output_type="$tmp_dir/plan-review-live-wrong-type.out"
  if PATH="$fake_bin:$PATH" "$SCRIPT_DIR/plan-review-live" --engine legacy --repo "$repo" --plan "$repo/.ai/plans/2026-02-19-000008-live-invalid.md" --resolve-file "$wrong_type" > "$output_type" 2>&1; then
    echo "Expected wrong-type resolve-file to fail" >&2
    exit 1
  fi
  assert_contains "$output_type" "contains non-string entry"
}

create_approved_plan() {
  local repo="$1"
  local plan_id="$2"
  local plan_path="$repo/.ai/plans/${plan_id}.md"
  mkdir -p "$repo/.ai/plans"
  cat > "$plan_path" <<EOF
---
id: $plan_id
status: APPROVED
repo_path: $repo
---

# Plan: $plan_id
EOF
  printf '%s\n' "$plan_path"
}

write_metadata_file() {
  local path="$1"
  local plan_id="$2"
  local plan_path="$3"
  local mode="$4"
  local ready="$5"
  local blocking="$6"
  local resolved="$7"
  local review_path="$8"
  cat > "$path" <<EOF
{
  "schema_version": 1,
  "plan_id": "$plan_id",
  "plan_path": "$plan_path",
  "mode": "$mode",
  "ready_for_implementation": $ready,
  "blocking_decisions": $blocking,
  "resolved_decisions": $resolved,
  "created_at": "2026-02-25T00:00:00+00:00",
  "review_markdown_path": "$review_path"
}
EOF
}

test_code_implement_blocks_when_metadata_missing() {
  local repo="$tmp_dir/repo-code-implement-missing"
  mkdir -p "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  local plan_path
  plan_path="$(create_approved_plan "$repo" "2026-02-19-000010-missing")"
  local output="$tmp_dir/code-implement-missing.out"

  if (cd "$repo" && PATH="$fake_bin:$PATH" "$SCRIPT_DIR/code-implement" --plan "$plan_path" > "$output" 2>&1); then
    echo "Expected code-implement to block on missing metadata" >&2
    exit 1
  fi

  assert_contains "$output" "review gate blocked implementation"
  assert_contains "$output" "Missing review metadata"
}

test_code_implement_blocks_when_metadata_invalid() {
  local repo="$tmp_dir/repo-code-implement-invalid"
  mkdir -p "$repo/.ai/plan-reviews"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  local plan_path
  plan_path="$(create_approved_plan "$repo" "2026-02-19-000011-invalid")"
  local review_path="$repo/.ai/plan-reviews/review.md"
  echo "review" > "$review_path"
  write_metadata_file \
    "$repo/.ai/plan-reviews/latest-2026-02-19-000011-invalid.json" \
    "wrong-id" \
    "$plan_path" \
    "batch" \
    "true" \
    "[]" \
    "[]" \
    "$review_path"

  local output="$tmp_dir/code-implement-invalid.out"
  if (cd "$repo" && PATH="$fake_bin:$PATH" "$SCRIPT_DIR/code-implement" --plan "$plan_path" > "$output" 2>&1); then
    echo "Expected code-implement to block on invalid metadata" >&2
    exit 1
  fi

  assert_contains "$output" "review gate blocked implementation"
  assert_contains "$output" "Metadata plan_id mismatch"
}

test_code_implement_blocks_when_unresolved_blockers_exist() {
  local repo="$tmp_dir/repo-code-implement-blockers"
  mkdir -p "$repo/.ai/plan-reviews"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  local plan_path
  plan_path="$(create_approved_plan "$repo" "2026-02-19-000012-blockers")"
  local review_path="$repo/.ai/plan-reviews/review.md"
  echo "review" > "$review_path"
  write_metadata_file \
    "$repo/.ai/plan-reviews/latest-2026-02-19-000012-blockers.json" \
    "2026-02-19-000012-blockers" \
    "$plan_path" \
    "live" \
    "false" \
    "[\"2B unresolved\"]" \
    "[\"1A\"]" \
    "$review_path"

  local output="$tmp_dir/code-implement-blockers.out"
  if (cd "$repo" && PATH="$fake_bin:$PATH" "$SCRIPT_DIR/code-implement" --plan "$plan_path" > "$output" 2>&1); then
    echo "Expected code-implement to block on unresolved blockers" >&2
    exit 1
  fi

  assert_contains "$output" "review gate blocked implementation"
  assert_contains "$output" "ready_for_implementation=false"
}

test_code_implement_allows_ready_metadata() {
  local repo="$tmp_dir/repo-code-implement-ready"
  mkdir -p "$repo/.ai/plan-reviews"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  local plan_path
  plan_path="$(create_approved_plan "$repo" "2026-02-19-000013-ready")"
  local review_path="$repo/.ai/plan-reviews/review.md"
  echo "review" > "$review_path"
  write_metadata_file \
    "$repo/.ai/plan-reviews/latest-2026-02-19-000013-ready.json" \
    "2026-02-19-000013-ready" \
    "$plan_path" \
    "live" \
    "true" \
    "[]" \
    "[\"1A\", \"2B\"]" \
    "$review_path"

  local output="$tmp_dir/code-implement-ready.out"
  if (cd "$repo" && PATH="$fake_bin:$PATH" "$SCRIPT_DIR/code-implement" --plan "$plan_path" > "$output" 2>&1); then
    echo "Expected code-implement to fail later due tmux in smoke environment" >&2
    exit 1
  fi

  assert_not_contains "$output" "review gate blocked implementation"
  assert_contains "$output" "Failed to create tmux session"
}

test_code_implement_force_bypasses_review_gate() {
  local repo="$tmp_dir/repo-code-implement-force"
  mkdir -p "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  local plan_path
  plan_path="$(create_approved_plan "$repo" "2026-02-19-000014-force")"
  local output="$tmp_dir/code-implement-force.out"

  if (cd "$repo" && PATH="$fake_bin:$PATH" "$SCRIPT_DIR/code-implement" --plan "$plan_path" --force > "$output" 2>&1); then
    echo "Expected code-implement to fail later due tmux in smoke environment" >&2
    exit 1
  fi

  assert_contains "$output" "--force enabled: bypassing plan-review readiness gate."
  assert_not_contains "$output" "review gate blocked implementation"
  assert_contains "$output" "Failed to create tmux session"
}

test_code_implement_accepts_metadata_from_non_tty_apply_flow() {
  local repo="$tmp_dir/repo-code-implement-from-auto-apply"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  local plan_path
  plan_path="$(create_approved_plan "$repo" "2026-02-19-000015-auto-apply-gate")"
  PATH="$fake_bin:$PATH" \
    "$SCRIPT_DIR/plan-review-live" --engine legacy --repo "$repo" --plan "$plan_path" --decisions "1A,2A,3A,4A" --blocking none > "$tmp_dir/plan-review-live-gate.out"

  local output="$tmp_dir/code-implement-auto-apply-gate.out"
  if (cd "$repo" && PATH="$fake_bin:$PATH" "$SCRIPT_DIR/code-implement" --plan "$plan_path" > "$output" 2>&1); then
    echo "Expected code-implement to fail later due tmux in smoke environment" >&2
    exit 1
  fi

  assert_not_contains "$output" "review gate blocked implementation"
  assert_contains "$output" "Failed to create tmux session"
}

test_code_implement_accepts_metadata_from_apply_mode() {
  local repo="$tmp_dir/repo-code-implement-from-apply-mode"
  mkdir -p "$repo/.ai/plans"
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@example.com
  git -C "$repo" config user.name smoke
  echo "hi" > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "init"

  local plan_path
  local output_file="$repo/.ai/plan-reviews/apply-output.md"
  plan_path="$(create_approved_plan "$repo" "2026-02-19-000016-apply-mode-gate")"
  PATH="$fake_bin:$PATH" \
    "$SCRIPT_DIR/code-plan-review" --repo "$repo" --plan "$plan_path" --mode apply --decisions "1A,2A,3A,4A" --blocking none --output "$output_file" > "$tmp_dir/plan-review-apply-gate.out"

  local latest_metadata="$repo/.ai/plan-reviews/latest-2026-02-19-000016-apply-mode-gate.json"
  [[ -f "$latest_metadata" ]] || { echo "Expected apply-mode metadata file" >&2; exit 1; }
  assert_contains "$latest_metadata" "\"mode\": \"live\""
  assert_contains "$latest_metadata" "\"ready_for_implementation\": true"

  local output="$tmp_dir/code-implement-apply-mode-gate.out"
  if (cd "$repo" && PATH="$fake_bin:$PATH" "$SCRIPT_DIR/code-implement" --plan "$plan_path" > "$output" 2>&1); then
    echo "Expected code-implement to fail later due tmux in smoke environment" >&2
    exit 1
  fi

  assert_not_contains "$output" "review gate blocked implementation"
  assert_contains "$output" "Failed to create tmux session"
}

test_invalid_mode_rejected
test_invalid_cli_rejected
test_review_prompt_pass_through
test_invalid_impl_mode_rejected
test_invalid_acp_enable_rejected
test_impl_direct_mode_uses_codex_exec
test_impl_uses_acpx_first_when_available
test_review_uses_codex_review_first
test_acp_agent_alias_forwarded
test_acpx_cmd_override_is_used
test_acp_disable_skips_acpx
test_code_plan_generates_artifact
test_safe_impl_claude_plan_mode_no_dangerous_skip
test_plan_review_generates_artifact
test_plan_review_output_parent_dirs_created
test_plan_review_live_lobster_default_engine
test_plan_review_live_lobster_resume_preserves_decisions
test_plan_review_live_generates_ready_metadata
test_plan_review_live_non_tty_auto_apply_with_flags
test_plan_review_live_resolution_inputs_override_allow_non_tty
test_plan_review_live_non_tty_auto_apply_with_resolve_file
test_plan_review_live_non_tty_requires_resolution_inputs
test_plan_review_live_rejects_invalid_resolve_file
test_plan_review_live_rejects_mixed_resolution_inputs
test_code_implement_blocks_when_metadata_missing
test_code_implement_blocks_when_metadata_invalid
test_code_implement_blocks_when_unresolved_blockers_exist
test_code_implement_allows_ready_metadata
test_code_implement_force_bypasses_review_gate
test_code_implement_accepts_metadata_from_non_tty_apply_flow
test_code_implement_accepts_metadata_from_apply_mode

printf 'Wrapper smoke tests passed.\n'
