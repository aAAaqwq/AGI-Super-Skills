#!/usr/bin/env bash
# safe-review.sh - Wrapper for claude/codex review commands
# Enforces timeout minimums and blocks --max-turns
set -euo pipefail

# Ensure standard tools are available on NixOS
export PATH="$PATH:/run/current-system/sw/bin"

# Configuration
MIN_REVIEW_TIMEOUT=${MIN_REVIEW_TIMEOUT:-600}
DEFAULT_TIMEOUT=${DEFAULT_TIMEOUT:-1200}
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/resolve-cli.sh"

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

error() { echo -e "${RED}❌ $1${NC}" >&2; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}" >&2; }

# Detect which CLI to use
CLI="${1:-}"
if [[ -z "$CLI" ]]; then
  error "Usage: safe-review.sh <claude|codex> [args...]"
  exit 1
fi

if [[ "$CLI" != "claude" && "$CLI" != "codex" ]]; then
  error "Unknown CLI: $CLI. Must be 'codex' or 'claude'."
  exit 1
fi

shift # Remove CLI name from args

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

# Parse timeout from environment or args
TIMEOUT="${TIMEOUT:-$DEFAULT_TIMEOUT}"

# Check minimum timeout for reviews
if [[ $TIMEOUT -lt $MIN_REVIEW_TIMEOUT ]]; then
  error "Timeout ${TIMEOUT}s is below minimum ${MIN_REVIEW_TIMEOUT}s for reviews."
  echo "  Reviews require adequate time for quality analysis."
  echo "  See: SKILL.md Rule 5"
  echo ""
  echo "  Fix: TIMEOUT=$MIN_REVIEW_TIMEOUT $0 $CLI $*"
  exit 1
fi

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

# For Claude CLI with -p flag, add --dangerously-skip-permissions to avoid hanging
EXTRA_ARGS=()
if [[ "$CLI" == "claude" ]]; then
  for arg in "$@"; do
    if [[ "$arg" == "-p" || "$arg" == "--print" ]]; then
      # Check if --dangerously-skip-permissions is already present
      if [[ ! " $* " =~ " --dangerously-skip-permissions " ]]; then
        EXTRA_ARGS+=("--dangerously-skip-permissions")
        warn "Adding --dangerously-skip-permissions to prevent permission prompt hangs"
      fi
      break
    fi
  done
fi

# Execute with timeout (use ${arr[@]+...} for older bash compatibility)
warn "Running $CLI with ${TIMEOUT}s timeout (min: ${MIN_REVIEW_TIMEOUT}s)"
exec timeout "${TIMEOUT}s" "$CLI_BIN" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} "$@"
