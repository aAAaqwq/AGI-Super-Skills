#!/usr/bin/env bash
# safe-impl.sh - Wrapper for implementation commands
# Enforces branch check and blocks --max-turns
set -euo pipefail

# Ensure standard tools are available on NixOS
export PATH="$PATH:/run/current-system/sw/bin"

# Configuration
MIN_IMPL_TIMEOUT=${MIN_IMPL_TIMEOUT:-180}
DEFAULT_TIMEOUT=${DEFAULT_TIMEOUT:-180}
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/resolve-cli.sh"

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

error() { echo -e "${RED}❌ $1${NC}" >&2; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}" >&2; }
ok() { echo -e "${GREEN}✅ $1${NC}" >&2; }

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

# Check for forbidden --max-turns flag
for arg in "$@"; do
  if [[ "$arg" == "--max-turns"* ]] || [[ "$arg" == "--max-turns="* ]]; then
    error "--max-turns is FORBIDDEN by coding-agent skill."
    echo "  Let the command complete naturally with adequate timeout."
    echo "  See: SKILL.md Rule 4"
    exit 1
  fi
done

# Check timeout command exists (not default on macOS)
if ! command -v timeout &>/dev/null; then
  error "'timeout' command not found. Install coreutils (brew install coreutils on macOS)."
  exit 1
fi

# Check we're not on main/master branch
BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [[ -z "$BRANCH" ]]; then
  error "Not in a git repository or no branch checked out."
  echo "  Implementation requires a git repository with a feature branch."
  exit 1
fi

PROTECTED_BRANCHES="main master"
for protected in $PROTECTED_BRANCHES; do
  if [[ "$BRANCH" == "$protected" ]]; then
    error "Cannot run implementation on '$BRANCH' branch."
    echo "  Create a feature branch first:"
    echo "    git checkout -b type/description"
    echo "  See: SKILL.md Rule 2"
    exit 1
  fi
done

ok "Branch check passed: $BRANCH"

# Parse timeout from environment
TIMEOUT="${TIMEOUT:-$DEFAULT_TIMEOUT}"

# Validate minimum timeout
if [[ $TIMEOUT -lt $MIN_IMPL_TIMEOUT ]]; then
  warn "Timeout ${TIMEOUT}s is below recommended ${MIN_IMPL_TIMEOUT}s"
fi

# Require explicit CLI specification
CLI="${1:-}"
if [[ -z "$CLI" ]]; then
  error "Usage: safe-impl.sh <codex|claude> [args...]"
  exit 1
fi

if [[ "$CLI" != "codex" && "$CLI" != "claude" ]]; then
  error "Unknown CLI: $CLI. Must be 'codex' or 'claude'."
  exit 1
fi

shift # Remove CLI name from args

# Validate CLI exists
CLI_BIN="$CLI"
if [[ "$CLI" == "claude" ]]; then
  if ! CLI_BIN="$(resolve_claude_bin)"; then
    if [[ -n "${CODING_AGENT_CLAUDE_BIN:-}" ]]; then
      error "CODING_AGENT_CLAUDE_BIN is set but not executable: ${CODING_AGENT_CLAUDE_BIN}"
    else
      error "Claude CLI not found (tried CODING_AGENT_CLAUDE_BIN, ~/.claude/local/claude, then PATH)."
    fi
    exit 1
  fi
elif ! command -v "$CLI" &>/dev/null; then
  error "CLI '$CLI' not found in PATH"
  exit 1
fi

# Codex implementation mode:
# - direct: run codex directly
# - tmux: require tmux transport
# - auto: tmux when attached to interactive TTY and tmux exists; otherwise direct
if [[ "$CLI" == "codex" ]]; then
  IMPL_MODE="$(resolve_impl_mode)"
  case "$IMPL_MODE" in
    direct)
      RUN_IN_TMUX=0
      ;;
    tmux)
      RUN_IN_TMUX=1
      ;;
    auto)
      if command -v tmux &>/dev/null && [[ -t 1 ]]; then
        RUN_IN_TMUX=1
      else
        RUN_IN_TMUX=0
      fi
      ;;
    *)
      error "Invalid CODING_AGENT_IMPL_MODE '$IMPL_MODE' (expected: direct|tmux|auto)"
      exit 1
      ;;
  esac

  if [[ "$RUN_IN_TMUX" == "1" ]]; then
    if ! command -v tmux &>/dev/null; then
      error "tmux not found in PATH. Install tmux or set CODING_AGENT_IMPL_MODE=direct."
      exit 1
    fi
    TMUX_RUN="$SCRIPT_DIR/tmux-run"
    if [[ ! -x "$TMUX_RUN" ]]; then
      error "tmux-run not found or not executable: $TMUX_RUN"
      exit 1
    fi
    warn "Running codex implementation in tmux with ${TIMEOUT}s timeout (mode: ${IMPL_MODE})"
    CODEX_TMUX_SESSION_PREFIX="${CODEX_TMUX_SESSION_PREFIX:-codex-impl}" \
      "$TMUX_RUN" timeout "${TIMEOUT}s" "$CLI" "$@"
    exit $?
  fi
fi

# For Claude CLI with -p flag, add --dangerously-skip-permissions to avoid hanging,
# unless running explicit plan permission mode.
EXTRA_ARGS=()
if [[ "$CLI" == "claude" ]]; then
  has_print_mode=0
  has_plan_permission_mode=0
  for arg in "$@"; do
    if [[ "$arg" == "-p" || "$arg" == "--print" ]]; then
      has_print_mode=1
    fi
    if [[ "$arg" == "--permission-mode" ]]; then
      has_plan_permission_mode=2
      continue
    fi
    if [[ "$has_plan_permission_mode" == "2" ]]; then
      if [[ "$arg" == "plan" ]]; then
        has_plan_permission_mode=1
      else
        has_plan_permission_mode=0
      fi
    fi
    if [[ "$arg" == "--permission-mode=plan" ]]; then
      has_plan_permission_mode=1
    fi
  done

  if [[ "$has_print_mode" == "1" && "$has_plan_permission_mode" != "1" ]]; then
    if [[ ! " $* " =~ " --dangerously-skip-permissions " ]]; then
      EXTRA_ARGS+=("--dangerously-skip-permissions")
      warn "Adding --dangerously-skip-permissions to prevent permission prompt hangs"
    fi
  fi
fi

# Execute with timeout (use ${arr[@]+...} for older bash compatibility)
warn "Running $CLI implementation with ${TIMEOUT}s timeout"
exec timeout "${TIMEOUT}s" "$CLI_BIN" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} "$@"
