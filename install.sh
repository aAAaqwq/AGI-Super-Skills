#!/usr/bin/env bash
# AGI Super Team — One-Click Deploy
# Usage: curl -sSL <raw-url> | bash -s -- [starter-kit] [agent-id]
#   or:  ./install.sh [starter-kit] [agent-id]
#
# Examples:
#   ./install.sh solo-founder          # Deploy solo-founder kit (CEO + PE + CCO)
#   ./install.sh solo-founder ceo      # Deploy only CEO from solo-founder kit
#   ./install.sh full-team             # Deploy all 12 agents
#   ./install.sh ceo                   # Deploy single CEO agent
#
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/aAAaqwq/AGI-Super-Team/main"
REPO_URL="https://github.com/aAAaqwq/AGI-Super-Team.git"
OPENCLAW_DIR="${HOME}/.openclaw"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Prerequisites ──────────────────────────────────────────────
check_prereqs() {
  command -v node &>/dev/null || err "Node.js not found. Install: https://nodejs.org/"
  command -v openclaw &>/dev/null || err "OpenClaw not found. Install: npm install -g openclaw"
  command -v git &>/dev/null || err "git not found."
  info "Prerequisites ✓"
}

# ── Clone or update repo ──────────────────────────────────────
ensure_repo() {
  local clone_dir="${1:-${HOME}/.agi-super-team}"
  if [[ -d "$clone_dir/.git" ]]; then
    info "Updating existing repo at $clone_dir"
    git -C "$clone_dir" pull --ff-only -q 2>/dev/null || warn "Git pull failed, using cached version"
  else
    info "Cloning AGI Super Team..."
    git clone --depth 1 "$REPO_URL" "$clone_dir" -q
  fi
  RETVAL_REPO="$clone_dir"
}

# ── Agent ID mapping ──────────────────────────────────────────
declare -A AGENT_MAP=(
  [ceo]=main [cto]=cto [pe]=pe [cpo]=cpo [cqo]=cqo [cmo]=cmo
  [cfo]=cfo [cdo]=cdo [cco]=cco [clo]=clo [cro]=cro [cso]=cso [coo]=coo
)

declare -A AGENT_NAMES=(
  [main]="CEO (Elon Musk)" [cto]="CTO (Jensen Huang)" [pe]="PE (Linus Torvalds)"
  [cpo]="CPO (Steve Jobs)" [cqo]="CQO (Jim Simons)" [cmo]="CMO (David Ogilvy)"
  [cfo]="CFO (Warren Buffett)" [cdo]="CDO (Nate Silver)" [cco]="CCO (MrBeast)"
  [clo]="CLO (Alan Dershowitz)" [cro]="CRO (Richard Feynman)" [cso]="CSO (Michael Dell)"
  [coo]="COO (Andy Grove)"
)

declare -A AGENT_MODELS=(
  [main]="zai/glm-5.1" [cto]="zai/glm-5.1" [pe]="zai/glm-5.1"
  [cpo]="zai/glm-5.1" [cqo]="zai/glm-5.1" [cmo]="zai/glm-5.1"
  [cfo]="zai/glm-5.1" [cdo]="zai/glm-5.1" [cco]="zai/glm-5.1"
  [clo]="zai/glm-5.1" [cro]="zai/glm-5.1" [cso]="zai/glm-5.1"
  [coo]="zai/glm-5.1"
)

# ── Skills for each agent (curated top skills) ────────────────
declare -A AGENT_SKILLS=(
  [main]="team-coordinator context-manager healthcheck daily-rhythm web-search project-planner"
  [pe]="react-expert tdd-workflow systematic-debugging code-review-quality github gh-issues docker-containerization deployment-automation kubernetes-specialist ghost-scan-code cli-developer"
  [cco]="xhs-publisher douyin-publisher gzh-publisher content-pipeline seo-writing"
  [cto]="api-design api-design-patterns architecture-decision architecture-patterns nginx-configuration"
  [cdo]="apify-ultimate-scraper web-search data-pipeline duckdb-analytics"
  [cmo]="seo-audit marketing-strategy growth-hacking competitor-analysis"
  [cfo]="financial-modeling budget-optimization cost-analysis"
  [cqo]="backtesting-system risk-management portfolio-optimization"
  [cro]="deep-research web-search scientific-method"
  [cpo]="prd-development user-story product-roadmap"
  [clo]="legal-review contract-analysis compliance-check"
  [cso]="sales-strategy customer-analysis crm-automation"
  [coo]="monitoring incident-response cost-optimization"
)

# ── Deploy a single agent ─────────────────────────────────────
deploy_agent() {
  local repo_dir="$1"
  local agent_key="$2"   # e.g. "ceo", "pe", "cco"
  local ws="${OPENCLAW_DIR}/workspace-${agent_key}"

  local display_name="${AGENT_NAMES[$agent_key]:-$agent_key}"
  info "Deploying ${display_name}..."

  # Create workspace
  mkdir -p "${ws}/skills" "${ws}/memory"

  # Copy persona files
  local src="${repo_dir}/agents/${agent_key}"
  if [[ -d "$src" ]]; then
    for f in SOUL.md AGENTS.md IDENTITY.md BOOTSTRAP.md MEMORY.md USER.md TOOLS.md WORKFLOW.md; do
      [[ -f "${src}/${f}" ]] && cp "${src}/${f}" "${ws}/"
    done
  else
    warn "Agent source not found: $src — skipping persona copy"
  fi

  # Copy curated skills
  local skill_list="${AGENT_SKILLS[$agent_key]:-}"
  if [[ -n "$skill_list" ]]; then
    for skill in $skill_list; do
      if [[ -d "${repo_dir}/skills/${skill}" ]]; then
        cp -r "${repo_dir}/skills/${skill}" "${ws}/skills/"
      fi
    done
  fi

  # Copy shared docs
  for f in CHARTER.md COLLABORATION.md; do
    [[ -f "${repo_dir}/${f}" ]] && cp "${repo_dir}/${f}" "${OPENCLAW_DIR}/agents/"
  done 2>/dev/null || true

  ok "Deployed ${display_name} → ${ws}"
}

# ── Starter Kits ──────────────────────────────────────────────
deploy_starter_kit() {
  local repo_dir="$1"
  local kit="$2"
  local filter="${3:-}"   # optional: deploy only one agent from kit

  local -a agents=()

  case "$kit" in
    solo-founder)
      agents=(ceo pe cco)
      ;;
    content-creator)
      agents=(cco cdo cmo)
      ;;
    quant-trader)
      agents=(cqo cdo cfo)
      ;;
    full-team)
      agents=(ceo cto pe cpo cqo cmo cfo cdo cco clo cro cso coo)
      ;;
    *)
      # Treat as agent alias
      local resolved="${AGENT_MAP[$kit]:-$kit}"
      agents=("$resolved")
      ;;
  esac

  # Filter to single agent if specified
  if [[ -n "$filter" ]]; then
    local resolved="${AGENT_MAP[$filter]:-$filter}"
    local found=0
    for a in "${agents[@]}"; do
      [[ "$a" == "$resolved" ]] && found=1
    done
    [[ "$found" -eq 1 ]] || err "Agent '$filter' not found in kit '$kit'"
    agents=("$resolved")
  fi

  info "Deploying kit: ${kit} (${#agents[@]} agent(s))"

  for a in "${agents[@]}"; do
    deploy_agent "$repo_dir" "$a"
  done

  echo ""
  ok "════════════════════════════════════════"
  ok " Kit '${kit}' deployed! ${#agents[@]} agent(s) ready"
  ok "════════════════════════════════════════"
  echo ""
  echo "Next steps:"
  echo "  1. Configure your API keys:  openclaw config"
  echo "  2. Restart the gateway:       openclaw gateway restart"
  echo "  3. Start chatting with your agent!"
  echo ""
  echo "Deployed agents:"
  for a in "${agents[@]}"; do
    echo "  • ${AGENT_NAMES[$a]:-$a} → ~/.openclaw/workspace-${a}/"
  done
}

# ── Main ──────────────────────────────────────────────────────
main() {
  echo ""
  echo "╔══════════════════════════════════════╗"
  echo "║     🏛️  AGI Super Team Deployer      ║"
  echo "║     727 Skills · 12 Agents            ║"
  echo "╚══════════════════════════════════════╝"
  echo ""

  check_prereqs

  local kit="${1:-solo-founder}"
  local agent_filter="${2:-}"

  # Ensure agents dir
  mkdir -p "${OPENCLAW_DIR}/agents"

  local repo_dir
  ensure_repo
  repo_dir="$RETVAL_REPO"

  deploy_starter_kit "$repo_dir" "$kit" "$agent_filter"
}

main "$@"
