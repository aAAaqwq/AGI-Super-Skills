#!/usr/bin/env bash
# hermes-remote-deploy — 通过 SSH 远程部署 Hermes Agent
# Hermes Agent by Nous Research — The Agent That Grows With You
# Prerequisites: ssh-copy-id 已完成，目标机器 SSH 已开
# Usage: ./deploy.sh <user@host> <provider> <api-key> [options]
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; }
step() { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }
info() { echo -e "${MAGENTA}[i]${NC} $*"; }

# ── Provider defaults ────────────────────────────────────────
declare -A PROVIDER_DEFAULTS
PROVIDER_DEFAULTS[deepseek_model]="deepseek/deepseek-v4-pro"
PROVIDER_DEFAULTS[deepseek_key]="DEEPSEEK_API_KEY"
PROVIDER_DEFAULTS[openai_model]="openai/gpt-4o"
PROVIDER_DEFAULTS[openai_key]="OPENAI_API_KEY"
PROVIDER_DEFAULTS[anthropic_model]="anthropic/claude-sonnet-4"
PROVIDER_DEFAULTS[anthropic_key]="ANTHROPIC_API_KEY"
PROVIDER_DEFAULTS[openrouter_model]="openrouter/anthropic/claude-sonnet-4"
PROVIDER_DEFAULTS[openrouter_key]="OPENROUTER_API_KEY"
PROVIDER_DEFAULTS[nous_model]="nous/hermes-3-70b"
PROVIDER_DEFAULTS[nous_key]="NOUS_API_KEY"

VALID_PROVIDERS="deepseek openai anthropic openrouter nous"

usage() {
  cat <<EOF
Usage: $0 <user@host> <provider> <api-key> [options]

Arguments:
  user@host        SSH target (e.g. root@my-vps or daniel@192.168.1.100)
  provider         Model provider: deepseek | openai | anthropic | openrouter | nous
  api-key          API key for the provider

Options:
  --model           Model ID (default: provider default)
  --branch          Hermes install branch (default: main)
  --skip-gateway    Skip gateway setup — CLI only mode
  --soul-path       Local SOUL.md file to deploy
  --dry-run         Print commands without executing

Provider defaults:
  deepseek    → ${PROVIDER_DEFAULTS[deepseek_model]}
  openai      → ${PROVIDER_DEFAULTS[openai_model]}
  anthropic   → ${PROVIDER_DEFAULTS[anthropic_model]}
  openrouter  → ${PROVIDER_DEFAULTS[openrouter_model]}
  nous        → ${PROVIDER_DEFAULTS[nous_model]}

Examples:
  $0 daniel@my-vps deepseek sk-2312xxxx
  $0 root@192.168.1.100 openai sk-proj-xxxx --model openai/gpt-4o
  $0 daniel@server openrouter sk-or-xxxx --skip-gateway
  $0 daniel@my-vps deepseek sk-xxxx --soul-path ./SOUL.md
EOF
  exit 1
}

# ── Parse args ──────────────────────────────────────────────
SSH_TARGET=""
PROVIDER=""
API_KEY=""
MODEL=""
BRANCH="main"
SKIP_GATEWAY=false
SOUL_PATH=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --skip-gateway) SKIP_GATEWAY=true; shift ;;
    --soul-path) SOUL_PATH="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage ;;
    *)
      if [[ -z "$SSH_TARGET" ]]; then SSH_TARGET="$1"
      elif [[ -z "$PROVIDER" ]]; then PROVIDER="$1"
      elif [[ -z "$API_KEY" ]]; then API_KEY="$1"
      else err "Unexpected argument: $1"; usage
      fi
      shift ;;
  esac
done

[[ -z "$SSH_TARGET" ]] && { err "Missing SSH target"; usage; }
[[ -z "$PROVIDER" ]] && { err "Missing provider"; usage; }
[[ -z "$API_KEY" ]] && { err "Missing API key"; usage; }

# Validate provider
if ! echo "$VALID_PROVIDERS" | grep -qw "$PROVIDER"; then
  err "Invalid provider: $PROVIDER"
  info "Valid providers: $VALID_PROVIDERS"
  exit 1
fi

# Resolve defaults
PROVIDER_MODEL="${PROVIDER_DEFAULTS[${PROVIDER}_model]}"
PROVIDER_KEY="${PROVIDER_DEFAULTS[${PROVIDER}_key]}"
[[ -n "$MODEL" ]] || MODEL="$PROVIDER_MODEL"

# ── SSH wrapper ──────────────────────────────────────────────
SSH_CMD="ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new $SSH_TARGET"

run_remote() {
  local desc="$1"; shift
  echo -e "${CYAN}  →${NC} $desc"
  if $DRY_RUN; then
    echo -e "    ${YELLOW}[dry-run]${NC} $SSH_CMD \"$*\""
  else
    $SSH_CMD "$*" || { err "Failed: $desc"; exit 1; }
  fi
}

# ══════════════════════════════════════════════════════════════
#  Banner
# ══════════════════════════════════════════════════════════════
echo ""
echo -e "${MAGENTA}  ╔═══════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}  ║   Hermes Agent · Remote Deploy v1.0      ║${NC}"
echo -e "${MAGENTA}  ║   The Agent That Grows With You          ║${NC}"
echo -e "${MAGENTA}  ║   Nous Research · hermes-agent            ║${NC}"
echo -e "${MAGENTA}  ╚═══════════════════════════════════════════╝${NC}"
echo ""
info "Target   : $SSH_TARGET"
info "Provider : $PROVIDER"
info "Model    : $MODEL"
info "Branch   : $BRANCH"
info "Gateway  : $([ "$SKIP_GATEWAY" = true ] && echo 'Skip' || echo 'Auto-setup')"
[[ -n "$SOUL_PATH" ]] && info "SOUL.md  : $SOUL_PATH"
echo ""

# ══════════════════════════════════════════════════════════════
#  Step 1 — Connectivity check
# ══════════════════════════════════════════════════════════════
step "Step 1/5: Checking SSH connectivity"

run_remote "Testing SSH connection" '
  echo "SSH_OK"
  echo "System : $(uname -s)"
  echo "Arch   : $(uname -m)"
  echo "Host   : $(hostname)"
  if [ -f /etc/os-release ]; then
    . /etc/os-release 2>/dev/null && echo "OS     : $PRETTY_NAME" || true
  fi
'

# ══════════════════════════════════════════════════════════════
#  Step 2 — Install Hermes
# ══════════════════════════════════════════════════════════════
step "Step 2/5: Installing Hermes Agent"

# Check for existing hermes
run_remote "Checking for existing Hermes installation" '
  if command -v hermes &>/dev/null; then
    echo "Hermes already installed: $(hermes --version 2>/dev/null || echo 'version-unknown')"
    echo "Location: $(which hermes)"
    echo "EXISTING=true"
  else
    echo "Hermes not found — will install fresh."
    echo "EXISTING=false"
  fi
'

# Check basic prerequisites
run_remote "Checking prerequisites" '
  echo "curl  : $(command -v curl &>/dev/null && echo OK || echo MISSING)"
  echo "git   : $(command -v git &>/dev/null && echo OK || echo MISSING)"
  echo "unzip : $(command -v unzip &>/dev/null && echo OK || echo MISSING)"
  echo "Shell : $SHELL"
'

# Install Hermes
run_remote "Running Hermes installer" "
  echo 'Downloading and installing Hermes Agent...'
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --branch $BRANCH 2>&1 | tail -20
  echo 'INSTALL_COMPLETE'
"

# Reload shell and verify
run_remote "Reloading shell and verifying installation" '
  # Reload shell config
  for rc in ~/.bashrc ~/.zshrc ~/.config/fish/config.fish; do
    [ -f "$rc" ] && source "$rc" 2>/dev/null || true
  done

  # Find hermes binary
  HERMES_BIN=""
  for candidate in \
    "$HOME/.hermes/hermes-agent/.venv/bin/hermes" \
    "$HOME/.local/bin/hermes" \
    "/usr/local/bin/hermes"; do
    if [ -x "$candidate" ]; then
      HERMES_BIN="$candidate"
      break
    fi
  done

  if [ -n "$HERMES_BIN" ]; then
    echo "Hermes binary: $HERMES_BIN"
    "$HERMES_BIN" --version 2>/dev/null || echo "version-check-skipped"
  elif command -v hermes &>/dev/null; then
    echo "Hermes found in PATH: $(which hermes)"
    hermes --version 2>/dev/null || echo "version-check-skipped"
  else
    echo "WARNING: hermes not found in PATH after install"
    echo "Check: ~/.hermes/hermes-agent/.venv/bin/hermes"
    ls -la ~/.hermes/hermes-agent/.venv/bin/hermes 2>/dev/null || echo "binary not found"
  fi
'

# ══════════════════════════════════════════════════════════════
#  Step 3 — Configure model provider
# ══════════════════════════════════════════════════════════════
step "Step 3/5: Configuring $PROVIDER model"

API_KEY_ESC=$(printf '%s' "$API_KEY" | sed "s/'/'\"'\"'/g")

run_remote "Setting model and API key" "
  # API key goes to .env automatically
  hermes config set $PROVIDER_KEY '$API_KEY_ESC'
  echo 'API key configured: $PROVIDER_KEY'

  # Model goes to config.yaml
  hermes config set model '$MODEL'
  echo 'Model set: $MODEL'

  # Verify config
  echo '--- Current config ---'
  hermes config 2>&1 | head -20 || echo '(config display skipped)'
"

# ══════════════════════════════════════════════════════════════
#  Step 4 — Deploy identity files (optional)
# ══════════════════════════════════════════════════════════════
step "Step 4/5: Deploying agent identity"

if [[ -n "$SOUL_PATH" && -f "$SOUL_PATH" ]]; then
  log "Deploying SOUL.md from $SOUL_PATH"
  if $DRY_RUN; then
    echo -e "    ${YELLOW}[dry-run]${NC} scp $SOUL_PATH $SSH_TARGET:~/.hermes/SOUL.md"
  else
    scp -o ConnectTimeout=10 "$SOUL_PATH" "$SSH_TARGET:~/.hermes/SOUL.md" || {
      warn "scp failed — trying inline copy"
      SOUL_CONTENT=$(cat "$SOUL_PATH" | sed "s/'/'\"'\"'/g")
      run_remote "Writing SOUL.md inline" "
        cat > ~/.hermes/SOUL.md << 'HERMES_SOUL_EOF'
$(cat "$SOUL_PATH")
HERMES_SOUL_EOF
        echo 'SOUL.md deployed'
      "
    }
    log "SOUL.md deployed"
  fi
else
  info "No SOUL.md provided — skipping identity deployment"
  info "Tip: use --soul-path ./SOUL.md to deploy agent identity"
fi

# ══════════════════════════════════════════════════════════════
#  Step 5 — Verify installation
# ══════════════════════════════════════════════════════════════
step "Step 5/5: Verifying Hermes installation"

run_remote "Running hermes doctor" '
  echo "=== Hermes Doctor ==="
  hermes doctor 2>&1 | head -30 || echo "doctor-check-completed"
  echo ""
  echo "=== Version ==="
  hermes --version 2>&1 || echo "version-unknown"
  echo ""
  echo "=== Config ==="
  hermes config 2>&1 | grep -E "(model|provider)" | head -5 || echo "(model config summary unavailable)"
'

# ══════════════════════════════════════════════════════════════
#  Gateway setup (optional)
# ══════════════════════════════════════════════════════════════
if [ "$SKIP_GATEWAY" = false ]; then
  step "Gateway: Configuring initial setup"

  run_remote "Running interactive setup (non-interactive basics)" '
    echo "Hermes gateway is available. To configure messaging platforms:"
    echo ""
    echo "  ssh '$SSH_TARGET'                 # connect to server"
    echo "  hermes gateway setup              # configure Telegram/Discord/etc"
    echo "  hermes gateway start              # start the gateway"
    echo ""
    echo "Or configure non-interactively:"
    echo "  hermes config set TELEGRAM_BOT_TOKEN <your-token>"
    echo "  hermes gateway start"
    echo ""
    echo "Gateway config directory: ~/.hermes/sessions/"
  '
else
  info "Gateway setup skipped (--skip-gateway)"
fi

# ══════════════════════════════════════════════════════════════
#  Done
# ══════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                     ║${NC}"
echo -e "${GREEN}║   Hermes Agent 远程部署完成！                         ║${NC}"
echo -e "${GREEN}║                                                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
log "Target   : $SSH_TARGET"
log "Provider : $PROVIDER"
log "Model    : $MODEL"
log "Home     : ~/.hermes/"
echo ""
echo "下一步 (在目标机器上执行):"
echo ""
echo "  # 连接服务器"
echo "  ssh $SSH_TARGET"
echo ""
echo "  # 开始聊天"
echo "  hermes"
echo ""
echo "  # 配置 Gateway 多平台接入"
echo "  hermes gateway setup"
echo "  hermes gateway start"
echo ""
echo "  # 查看帮助"
echo "  hermes --help"
echo "  hermes config"
echo "  hermes doctor"
echo ""
echo "  文档: https://hermes-agent.nousresearch.com/docs/"
