#!/usr/bin/env bash
# safe-fallback.sh - Try tools in order, report blocker if all fail
# NEVER falls back to direct edits - that's a Rule 1 violation
set -euo pipefail

# Ensure standard tools are available on NixOS
export PATH="$PATH:/run/current-system/sw/bin"

# Configuration
MODE="${1:-impl}"  # impl or review
shift || true

if [[ "$MODE" != "impl" && "$MODE" != "review" ]]; then
  echo "Error: invalid mode '$MODE' (expected: impl|review)" >&2
  echo "Usage: safe-fallback.sh <impl|review> \"prompt...\"" >&2
  exit 1
fi

PROMPT="${*:-}"
if [[ -z "$PROMPT" ]]; then
  echo "Usage: safe-fallback.sh <impl|review> \"prompt...\""
  echo ""
  echo "Examples:"
  echo "  safe-fallback.sh impl \"Implement feature X\""
  echo "  safe-fallback.sh review \"Review this PR for bugs and security issues\""
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/resolve-cli.sh"

# Timeouts
IMPL_TIMEOUT=${IMPL_TIMEOUT:-180}
REVIEW_TIMEOUT=${REVIEW_TIMEOUT:-1200}
TIMEOUT=$([[ "$MODE" == "review" ]] && echo "$REVIEW_TIMEOUT" || echo "$IMPL_TIMEOUT")

# Gemini fallback is opt-in only.
GEMINI_FALLBACK_ENABLE=${GEMINI_FALLBACK_ENABLE:-0}
if [[ "$GEMINI_FALLBACK_ENABLE" != "0" && "$GEMINI_FALLBACK_ENABLE" != "1" ]]; then
  echo "Error: GEMINI_FALLBACK_ENABLE must be 0 or 1" >&2
  exit 1
fi

# ACP-first routing is enabled by default.
CODING_AGENT_ACP_ENABLE=${CODING_AGENT_ACP_ENABLE:-1}
if [[ "$CODING_AGENT_ACP_ENABLE" != "0" && "$CODING_AGENT_ACP_ENABLE" != "1" ]]; then
  echo "Error: CODING_AGENT_ACP_ENABLE must be 0 or 1" >&2
  exit 1
fi
CODING_AGENT_ACP_AGENT=${CODING_AGENT_ACP_AGENT:-codex}

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

error() { echo -e "${RED}❌ $1${NC}" >&2; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}" >&2; }
ok() { echo -e "${GREEN}✅ $1${NC}" >&2; }
info() { echo -e "${CYAN}ℹ️  $1${NC}" >&2; }

resolve_impl_mode() {
  if [[ -n "${CODING_AGENT_IMPL_MODE:-}" ]]; then
    printf '%s\n' "${CODING_AGENT_IMPL_MODE}"
    return 0
  fi

  # Legacy compatibility knobs.
  if [[ "${CODEX_TMUX_DISABLE:-0}" == "1" ]]; then
    printf 'direct\n'
    return 0
  fi
  if [[ "${CODEX_TMUX_REQUIRED:-0}" == "1" ]]; then
    printf 'tmux\n'
    return 0
  fi

  printf 'direct\n'
}

detect_base_branch() {
  local base_branch="main"
  if git rev-parse --git-dir &>/dev/null; then
    base_branch="$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')"
    if [[ -z "$base_branch" ]]; then
      for candidate in main master trunk; do
        if git show-ref --verify --quiet "refs/heads/${candidate}" || \
           git show-ref --verify --quiet "refs/remotes/origin/${candidate}"; then
          base_branch="$candidate"
          break
        fi
      done
    fi
    if [[ -z "$base_branch" ]]; then
      base_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
    fi
  fi

  printf '%s\n' "$base_branch"
}

# Track failures (portable array init)
FAILURES=()

build_acpx_prompt() {
  if [[ "$MODE" == "review" ]]; then
    printf '%s\n' "$PROMPT"
    return 0
  fi

  printf '%s\n' "$PROMPT"
}

try_acpx() {
  if [[ "$CODING_AGENT_ACP_ENABLE" != "1" ]]; then
    FAILURES+=("ACPX: disabled (set CODING_AGENT_ACP_ENABLE=1 to enable)")
    return 1
  fi

  local acpx_bin
  if ! acpx_bin="$(resolve_acpx_bin)"; then
    if [[ -n "${CODING_AGENT_ACPX_CMD:-}" ]]; then
      FAILURES+=("ACPX: CODING_AGENT_ACPX_CMD is set but not executable (${CODING_AGENT_ACPX_CMD})")
    else
      FAILURES+=("ACPX: not found (CODING_AGENT_ACPX_CMD, PATH)")
    fi
    return 1
  fi

  if ! command -v timeout &>/dev/null; then
    FAILURES+=("ACPX: timeout command not available")
    return 1
  fi

  local acpx_prompt
  acpx_prompt="$(build_acpx_prompt)"

  info "Trying ACPX (${CODING_AGENT_ACP_AGENT})..."
  if timeout "${TIMEOUT}s" "$acpx_bin" "$CODING_AGENT_ACP_AGENT" exec --cwd "$PWD" --format quiet "$acpx_prompt"; then
    ok "ACPX succeeded"
    return 0
  fi

  FAILURES+=("ACPX: exec failed or timeout")
  return 1
}

# Try Codex CLI in tmux (implementation only)
try_codex_tmux() {
  if [[ "$MODE" != "impl" ]]; then
    FAILURES+=("Codex tmux: unsupported in review mode")
    return 1
  fi

  info "Trying Codex CLI in tmux..."
  if "$SCRIPT_DIR/code-implement" "$PROMPT"; then
    ok "Codex tmux session started"
    return 0
  fi

  FAILURES+=("Codex tmux: failed to start")
  return 1
}

# Try Codex CLI (direct, no tmux)
try_codex_cli_direct() {
  info "Trying Codex CLI (direct)..."
  if command -v codex &>/dev/null; then
    if ! command -v timeout &>/dev/null; then
      FAILURES+=("Codex CLI: timeout not installed")
      return 1
    fi

    if [[ "$MODE" == "review" ]]; then
      local base_branch
      base_branch="$(detect_base_branch)"

      if timeout "${TIMEOUT}s" codex review --base "$base_branch" --title "${PROMPT:0:100}" "$PROMPT"; then
        ok "Codex CLI review succeeded"
        return 0
      fi

      FAILURES+=("Codex CLI: review failed or timeout")
      return 1
    fi

    if timeout "${TIMEOUT}s" codex --yolo exec "$PROMPT"; then
      ok "Codex CLI implementation succeeded"
      return 0
    fi

    FAILURES+=("Codex CLI: exec failed or timeout")
    return 1
  fi

  FAILURES+=("Codex CLI: codex not installed")
  return 1
}

# Try Claude CLI
try_claude_cli() {
  info "Trying Claude CLI (timeout: ${TIMEOUT}s, skip-permissions)..."
  local claude_bin
  if claude_bin="$(resolve_claude_bin)"; then
    if command -v timeout &>/dev/null; then
      # Use --dangerously-skip-permissions to avoid hanging on permission prompts
      if timeout "${TIMEOUT}s" "$claude_bin" -p --dangerously-skip-permissions "$PROMPT"; then
        ok "Claude CLI succeeded"
        return 0
      fi

      FAILURES+=("Claude CLI: timeout or error (${TIMEOUT}s)")
    else
      FAILURES+=("Claude CLI: timeout command not available")
    fi
  else
    if [[ -n "${CODING_AGENT_CLAUDE_BIN:-}" ]]; then
      FAILURES+=("Claude CLI: CODING_AGENT_CLAUDE_BIN is set but not executable (${CODING_AGENT_CLAUDE_BIN})")
    else
      FAILURES+=("Claude CLI: not found (CODING_AGENT_CLAUDE_BIN, ~/.claude/local/claude, PATH)")
    fi
  fi

  return 1
}

# Try Gemini CLI (opt-in only)
try_gemini_cli() {
  if [[ "$GEMINI_FALLBACK_ENABLE" != "1" ]]; then
    FAILURES+=("Gemini CLI: disabled (set GEMINI_FALLBACK_ENABLE=1 to enable)")
    return 1
  fi

  info "Trying Gemini CLI (timeout: ${TIMEOUT}s)..."
  if command -v gemini &>/dev/null; then
    if command -v timeout &>/dev/null; then
      if timeout "${TIMEOUT}s" gemini -y "$PROMPT"; then
        ok "Gemini CLI succeeded"
        return 0
      fi

      FAILURES+=("Gemini CLI: timeout or error (${TIMEOUT}s)")
    else
      FAILURES+=("Gemini CLI: timeout command not available")
    fi
  else
    FAILURES+=("Gemini CLI: gemini not installed")
  fi

  return 1
}

# Report blocker (all to stderr)
report_blocker() {
  echo "" >&2
  error "BLOCKED: All tools unavailable for mode '$MODE'"
  echo "" >&2
  echo "Failures:" >&2
  for failure in "${FAILURES[@]}"; do
    echo "  - $failure" >&2
  done
  echo "" >&2
  echo "Options:" >&2
  echo "  a) Wait for tool availability (e.g., Codex usage limit reset)" >&2
  echo "  b) User manually runs: codex --yolo exec \"$PROMPT\"" >&2
  echo "  c) User explicitly authorizes override: 'Override Rule 1 for this task'" >&2
  echo "" >&2
  echo "⛔ DO NOT use direct file edits - this is a Rule 1 violation" >&2
  exit 1
}

# Main execution
main() {
  # All status to stderr so stdout only has tool output
  echo "Mode: $MODE | Timeout: ${TIMEOUT}s" >&2
  echo "ACP routing: $CODING_AGENT_ACP_ENABLE (agent: $CODING_AGENT_ACP_AGENT)" >&2
  echo "Gemini fallback: $GEMINI_FALLBACK_ENABLE" >&2

  if [[ "$MODE" == "review" ]]; then
    try_codex_cli_direct && exit 0
    warn "Codex CLI unavailable for review, trying ACP fallback..."

    try_acpx && exit 0
    warn "ACPX unavailable for review, trying next..."
  else
    try_acpx && exit 0
    warn "ACPX unavailable, trying CLI fallback chain..."

    impl_mode="$(resolve_impl_mode)"
    case "$impl_mode" in
      direct|tmux|auto)
        ;;
      *)
        error "Invalid CODING_AGENT_IMPL_MODE '$impl_mode' (expected: direct|tmux|auto)"
        exit 1
        ;;
    esac

    if [[ "$impl_mode" == "auto" ]]; then
      if command -v tmux &>/dev/null && [[ -t 1 ]]; then
        impl_mode="tmux"
      else
        impl_mode="direct"
      fi
    fi

    echo "Implementation mode: $impl_mode" >&2

    if [[ "$impl_mode" == "tmux" ]]; then
      try_codex_tmux && exit 0
      warn "Codex tmux unavailable, trying direct CLI..."
      try_codex_cli_direct && exit 0
      warn "Codex direct CLI unavailable, trying next..."
    else
      try_codex_cli_direct && exit 0
      warn "Codex direct CLI unavailable, trying tmux..."
      try_codex_tmux && exit 0
      warn "Codex tmux unavailable, trying next..."
    fi
  fi

  try_claude_cli && exit 0
  warn "Claude CLI unavailable..."

  try_gemini_cli && exit 0
  warn "Gemini CLI unavailable..."

  # All tools failed
  report_blocker
}

main
