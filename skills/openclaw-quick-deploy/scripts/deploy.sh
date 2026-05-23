#!/usr/bin/env bash
# openclaw-quick-deploy — 通过 SSH 远程部署 OpenClaw 系统
# Prerequisites: ssh-copy-id 已完成，目标 Mac 已开 Remote Login
# Usage: ./deploy.sh <user@host> <api-key> [--model deepseek/deepseek-v4-pro]
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; }
step() { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

usage() {
  cat <<EOF
Usage: $0 <user@host> <api-key> [options]

Arguments:
  user@host        SSH target (e.g. daniel@mac-m4-daniel or user@192.168.1.100)
  api-key          DeepSeek API key (sk-xxxx)

Options:
  --model           Model ID (default: deepseek/deepseek-v4-pro)
  --provider        Provider name in config (default: deepseek)
  --base-url        API base URL (default: https://api.deepseek.com/v1)
  --node-version    Node.js version hint (default: v24)
  --workspace-repo  Git repo URL (default: https://github.com/shenjj2025-oss/openclaw-team.git)
  --dry-run         Print commands without executing

Example:
  $0 daniel@mac-m4-daniel sk-xxxx
  $0 peter@192.168.1.100 sk-xxxx --model deepseek/deepseek-chat
EOF
  exit 1
}

# ── Parse args ──────────────────────────────────────────────
SSH_TARGET=""
API_KEY=""
MODEL="deepseek/deepseek-v4-pro"
PROVIDER="deepseek"
BASE_URL="https://api.deepseek.com/v1"
NODE_VERSION="v24"
WORKSPACE_REPO="https://github.com/shenjj2025-oss/openclaw-team.git"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --provider) PROVIDER="$2"; shift 2 ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    --node-version) NODE_VERSION="$2"; shift 2 ;;
    --workspace-repo) WORKSPACE_REPO="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage ;;
    *)
      if [[ -z "$SSH_TARGET" ]]; then SSH_TARGET="$1"
      elif [[ -z "$API_KEY" ]]; then API_KEY="$1"
      else err "Unexpected argument: $1"; usage
      fi
      shift ;;
  esac
done

[[ -z "$SSH_TARGET" || -z "$API_KEY" ]] && usage

# ── SSH wrapper ──────────────────────────────────────────────
SSH_CMD="ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new $SSH_TARGET"

run_remote() {
  local desc="$1"; shift
  echo -e "${CYAN}  →${NC} $desc"
  if $DRY_RUN; then
    echo "    [dry-run] $SSH_CMD \"$*\""
  else
    $SSH_CMD "$*" || { err "Failed: $desc"; exit 1; }
  fi
}

# ══════════════════════════════════════════════════════════════
#  Step 1 — Connectivity check
# ══════════════════════════════════════════════════════════════
step "Step 1/5: Checking SSH connectivity"
run_remote "Testing SSH connection" "echo SSH_OK && uname -a"

# ══════════════════════════════════════════════════════════════
#  Step 2 — Install / update OpenClaw
# ══════════════════════════════════════════════════════════════
step "Step 2/5: Installing latest OpenClaw"

run_remote "Checking Node.js" '
  if command -v node &>/dev/null; then
    echo "Node.js: $(node --version)"
  elif command -v nvm &>/dev/null || [ -s "$HOME/.nvm/nvm.sh" ]; then
    export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    echo "Node.js (nvm): $(node --version)"
  else
    echo "NODE_NOT_FOUND"
  fi
'

run_remote "Installing/updating OpenClaw" '
  if command -v npm &>/dev/null; then
    npm install -g openclaw@latest 2>&1 | tail -5
  elif command -v nvm &>/dev/null || [ -s "$HOME/.nvm/nvm.sh" ]; then
    export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    npm install -g openclaw@latest 2>&1 | tail -5
  else
    echo "ERROR: npm not found — install Node.js first"
    exit 1
  fi
  echo "OpenClaw: $(openclaw --version 2>/dev/null || echo version-unknown)"
'

# ══════════════════════════════════════════════════════════════
#  Step 3 — Clone workspace repo
# ══════════════════════════════════════════════════════════════
step "Step 3/5: Cloning openclaw-team workspace"

run_remote "Cloning workspace repo" "
  mkdir -p ~/.openclaw/workspace
  if [ -d ~/.openclaw/workspace/.git ]; then
    echo 'Workspace already has .git — pulling latest...'
    cd ~/.openclaw/workspace && git pull 2>&1 | tail -3
  else
    # Backup existing non-git workspace if present
    if [ -f ~/.openclaw/workspace/AGENTS.md ] || [ -f ~/.openclaw/workspace/SOUL.md ]; then
      BACKUP_DIR=~/.openclaw/workspace.bak.\$(date +%Y%m%d_%H%M%S)
      echo \"Backing up existing workspace to \$BACKUP_DIR\"
      mkdir -p \"\$BACKUP_DIR\" && cp -r ~/.openclaw/workspace/* \"\$BACKUP_DIR/\" 2>/dev/null || true
    fi
    rm -rf ~/.openclaw/workspace
    git clone $WORKSPACE_REPO ~/.openclaw/workspace 2>&1 | tail -3
  fi
"

# ══════════════════════════════════════════════════════════════
#  Step 4 — Deploy agent configs
# ══════════════════════════════════════════════════════════════
step "Step 4/5: Deploying agent configurations"

run_remote "Copying agent configs" '
  WORKSPACE=~/.openclaw/workspace
  if [ -d "$WORKSPACE/agents" ]; then
    echo "Found agents directory — copying to workspace root..."
    cp -r "$WORKSPACE/agents"/* ~/.openclaw/workspace/ 2>/dev/null || true
    echo "Agents deployed."
    ls ~/.openclaw/workspace/*.md 2>/dev/null | head -10 || echo "(no .md files in workspace root)"
  elif [ -d "$WORKSPACE/workspace" ]; then
    echo "Found workspace subdirectory — deploying from there..."
    cp -r "$WORKSPACE/workspace"/* ~/.openclaw/workspace/ 2>/dev/null || true
    echo "Configs deployed."
    ls ~/.openclaw/workspace/*.md 2>/dev/null | head -10 || echo "(no .md files in workspace root)"
  else
    echo "Using repo root as workspace directly — no copy needed."
    ls "$WORKSPACE"/*.md 2>/dev/null | head -10 || echo "(listing repo root .md files)"
  fi
'

# ══════════════════════════════════════════════════════════════
#  Step 5 — Configure model as default
# ══════════════════════════════════════════════════════════════
step "Step 5/5: Configuring $MODEL as default model"

# Escape the key for safe shell embedding
API_KEY_ESC=$(printf '%s' "$API_KEY" | sed "s/'/'\"'\"'/g")

run_remote "Writing model config" "
  openclaw config set agents.defaults.modelPrimary '$MODEL'
  openclaw config set models.providers.${PROVIDER}.baseUrl '$BASE_URL'
  openclaw config set models.providers.${PROVIDER}.apiKey '$API_KEY_ESC'
  openclaw config set agents.defaults.defaultAgent 'main'
  echo 'Model configured: $MODEL'
"

run_remote "Verifying OpenClaw status" '
  openclaw status 2>&1 || echo "Note: openclaw status returned non-zero (may need gateway restart)"
'

# ══════════════════════════════════════════════════════════════
#  Done
# ══════════════════════════════════════════════════════════════
echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "  OpenClaw 快速部署完成！"
log "  目标: $SSH_TARGET"
log "  模型: $MODEL"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "下一步 (在目标机器上执行):"
echo "  openclaw gateway restart"
echo "  openclaw onboard    # 如需配置 Telegram 等 channel"
