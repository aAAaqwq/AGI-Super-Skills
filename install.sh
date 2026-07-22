#!/usr/bin/env bash
# AGI Super Team — One-Click Deploy
# Usage: curl -sSL <raw-url> | bash -s -- [--apply] [starter-kit] [agent-id]
#   or:  ./install.sh [--source PATH] [--destination PATH] [--apply] [starter-kit] [agent-id]
#
# Examples:
#   ./install.sh solo-founder          # Preview solo-founder kit (CEO + PE + CCO)
#   ./install.sh --apply solo-founder  # Deploy the solo-founder kit
#   ./install.sh --apply full-team     # Deploy all 14 agents
#   ./install.sh --apply ceo           # Deploy single CEO agent
#
# ── 推荐方式 / Recommended ──────────────────────────────────────────
# 现在首选 harness 原生安装（无需本脚本）：
#   Claude Code (推荐): /plugin install aAAaqwq/AGI-Super-Team
#   或直接 clone:
#     git clone --depth 1 https://github.com/aAAaqwq/AGI-Super-Team.git ~/.agi-super-team
#
# 本脚本 (install.sh) 是多 harness 的通用部署器，仍可用于批量部署 starter
# kit 到本地工作区。下文依赖 OpenClaw CLI 的步骤（openclaw config /
# gateway restart 等）标注为 (legacy)，仅当你的环境仍运行 OpenClaw harness
# 时需要；OpenClaw 已 discontinued，新用户请使用 Claude Code / Codex /
# Cursor / Hermes 等 harness 原生方式。
# ─────────────────────────────────────────────────────────────────────
#
set -euo pipefail

REPO_URL="https://github.com/aAAaqwq/AGI-Super-Team.git"
OPENCLAW_DIR="${AGI_SUPER_TEAM_DESTINATION:-${HOME}/.openclaw}"
SOURCE_DIR="${AGI_SUPER_TEAM_SOURCE:-}"
APPLY=0
MANIFEST_PATH=""
DEPLOY_ROOT=""
INSTALL_STAGE=""

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Prerequisites ──────────────────────────────────────────────
check_prereqs() {
  if [[ -z "$SOURCE_DIR" && "$APPLY" -eq 1 ]]; then
    command -v git &>/dev/null || err "git not found."
  fi
  # (legacy) OpenClaw CLI is OPTIONAL — the script works with any harness
  # (Claude Code / Codex / Cursor / Hermes). Only needed if your environment
  # still runs the (discontinued) OpenClaw harness. Warn instead of failing.
  if ! command -v openclaw &>/dev/null; then
    warn "(legacy) openclaw CLI not found — OK for Claude Code / Codex / Cursor / Hermes. Only required for the discontinued OpenClaw harness."
  fi
  info "Prerequisites ✓"
}

# ── Clone or update repo ──────────────────────────────────────
ensure_repo() {
  if [[ -n "$SOURCE_DIR" ]]; then
    [[ -d "$SOURCE_DIR/agents" && -d "$SOURCE_DIR/skills" ]] \
      || err "Local source is not an AGI Super Team checkout: $SOURCE_DIR"
    RETVAL_REPO="$SOURCE_DIR"
    return
  fi

  if [[ "$APPLY" -eq 0 ]]; then
    info "[PREVIEW] Would clone or update ${REPO_URL} at ${HOME}/.agi-super-team"
    RETVAL_REPO=""
    return
  fi

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
resolve_agent() { printf '%s\n' "$1"; }

manifest_query() {
  local query="$1"
  local identifier="${2:-}"
  node - "$MANIFEST_PATH" "$query" "$identifier" <<'NODE'
const fs = require('fs');
const [manifestPath, query, identifier] = process.argv.slice(2);
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const agent = manifest.agents.find((entry) => entry.id === identifier);
const kit = manifest.kits.find((entry) => entry.id === identifier);

switch (query) {
  case 'agent-exists':
    process.stdout.write(agent ? 'yes\n' : 'no\n');
    break;
  case 'agent-name':
    if (!agent) process.exit(2);
    process.stdout.write(`${agent.name}\n`);
    break;
  case 'agent-path':
    if (!agent) process.exit(2);
    process.stdout.write(`${agent.path}\n`);
    break;
  case 'required':
  case 'optional':
  case 'recommendedExternal':
    if (!agent) process.exit(2);
    process.stdout.write(agent.skills[query].map(String).join('\n'));
    if (agent.skills[query].length) process.stdout.write('\n');
    break;
  case 'kit-agents':
    if (!kit) process.exit(2);
    process.stdout.write(kit.agents.map(String).join('\n'));
    if (kit.agents.length) process.stdout.write('\n');
    break;
  case 'kit-exists':
    process.stdout.write(kit ? 'yes\n' : 'no\n');
    break;
  default:
    process.exit(2);
}
NODE
}

load_team_manifest() {
  local repo_dir="$1"
  local candidate="${repo_dir}/config/team-manifest.json"

  if [[ -n "$repo_dir" && -L "$candidate" ]]; then
    err "Team manifest must not be a symlink: $candidate"
  fi
  if [[ -n "$repo_dir" && -f "$candidate" ]]; then
    command -v node &>/dev/null || err "Node.js is required to read $candidate"
    MANIFEST_PATH="$candidate"
    node -e 'const m=require(process.argv[1]); if(m.schemaVersion!==1 || !Array.isArray(m.agents) || !Array.isArray(m.kits)) process.exit(1)' "$MANIFEST_PATH" \
      || err "Invalid team manifest: $MANIFEST_PATH"
    info "Using team manifest: $MANIFEST_PATH"
  fi
}

agent_name() {
  if [[ -n "$MANIFEST_PATH" ]]; then
    manifest_query agent-name "$1"
    return
  fi
  case "$1" in
    ceo) printf '%s\n' "CEO (Elon Musk)" ;; cto) printf '%s\n' "CTO (Jensen Huang)" ;;
    pe) printf '%s\n' "PE (Linus Torvalds)" ;; cpo) printf '%s\n' "CPO (Steve Jobs)" ;;
    cqo) printf '%s\n' "CQO (Jim Simons)" ;; cmo) printf '%s\n' "CMO (David Ogilvy)" ;;
    cfo) printf '%s\n' "CFO (Warren Buffett)" ;; cdo) printf '%s\n' "CDO (Nate Silver)" ;;
    cco) printf '%s\n' "CCO (MrBeast)" ;; clo) printf '%s\n' "CLO (Alan Dershowitz)" ;;
    cro) printf '%s\n' "CRO (Richard Feynman)" ;; cso) printf '%s\n' "CSO (Michael Dell)" ;;
    coo) printf '%s\n' "COO (Andy Grove)" ;; governor) printf '%s\n' "Governor" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

# ── Skills for each agent (curated top skills) ────────────────
agent_skills() {
  if [[ -n "$MANIFEST_PATH" ]]; then
    manifest_query required "$1"
    return
  fi
  case "$1" in
  ceo) printf '%s\n' "team-coordinator context-manager healthcheck web-search project-planner" ;;
  pe) printf '%s\n' "react-expert tdd-workflow systematic-debugging code-review-quality github gh-issues deployment-automation kubernetes-specialist ghost-scan-code cli-developer" ;;
  cco) printf '%s\n' "xhs-publisher douyin-publisher" ;;
  cto) printf '%s\n' "api-design api-design-patterns architecture-decision architecture-patterns nginx-configuration" ;;
  cdo) printf '%s\n' "apify-ultimate-scraper web-search" ;;
  cmo) printf '%s\n' "seo-audit" ;;
  cfo|cqo) printf '\n' ;;
  cro) printf '%s\n' "deep-research web-search" ;;
  cpo) printf '%s\n' "prd-development user-story" ;;
  clo) printf '%s\n' "legal-review" ;;
  cso) printf '%s\n' "crm-automation" ;;
  coo) printf '%s\n' "cost-optimization" ;;
  *) printf '\n' ;;
  esac
}

agent_recommended_external_skills() {
  if [[ -n "$MANIFEST_PATH" ]]; then
    manifest_query recommendedExternal "$1"
    return
  fi
  case "$1" in
    ceo) printf '%s\n' "daily-rhythm" ;;
    pe) printf '%s\n' "docker-containerization" ;;
    cco) printf '%s\n' "gzh-publisher content-pipeline seo-writing" ;;
    cdo) printf '%s\n' "data-pipeline duckdb-analytics" ;;
    cmo) printf '%s\n' "marketing-strategy growth-hacking competitor-analysis" ;;
    cfo) printf '%s\n' "financial-modeling budget-optimization cost-analysis" ;;
    cqo) printf '%s\n' "backtesting-system risk-management portfolio-optimization" ;;
    cro) printf '%s\n' "scientific-method" ;;
    cpo) printf '%s\n' "product-roadmap" ;;
    clo) printf '%s\n' "contract-analysis compliance-check" ;;
    cso) printf '%s\n' "sales-strategy customer-analysis" ;;
    coo) printf '%s\n' "monitoring incident-response" ;;
    *) printf '\n' ;;
  esac
}

agent_optional_skills() {
  if [[ -n "$MANIFEST_PATH" ]]; then
    manifest_query optional "$1"
  else
    printf '\n'
  fi
}

agent_source_path() {
  if [[ -n "$MANIFEST_PATH" ]]; then
    manifest_query agent-path "$1"
  else
    printf 'agents/%s\n' "$1"
  fi
}

report_recommended_external_skills() {
  local agent_key skill count=0
  for agent_key in "$@"; do
    for skill in $(agent_recommended_external_skills "$agent_key"); do
      count=$((count + 1))
    done
  done
  if [[ "$count" -gt 0 ]]; then
    info "${count} recommended external skill(s) are not bundled; see the team manifest for details."
  fi
}

preflight_agents() {
  local repo_dir="$1"
  shift
  local agent_key src skill skill_list optional_skill_list source_name source_file linked_entry

  [[ -n "$repo_dir" ]] || return 0
  for agent_key in "$@"; do
    src="${repo_dir}/$(agent_source_path "$agent_key")"
    [[ ( -e "$src" || -L "$src" ) && -d "$src" && ! -L "$src" ]] \
      || err "Agent source must be a real directory: $src"
    for source_name in SOUL.md AGENTS.md IDENTITY.md BOOTSTRAP.md MEMORY.md USER.md TOOLS.md WORKFLOW.md; do
      source_file="${src}/${source_name}"
      if [[ -e "$source_file" || -L "$source_file" ]]; then
        [[ -f "$source_file" && ! -L "$source_file" ]] \
          || err "Source file must be a regular non-symlink: $source_file"
      fi
    done
    skill_list=$(agent_skills "$agent_key")
    optional_skill_list=$(agent_optional_skills "$agent_key")
    for skill in $skill_list $optional_skill_list; do
      [[ ( -e "${repo_dir}/skills/${skill}" || -L "${repo_dir}/skills/${skill}" ) \
          && -d "${repo_dir}/skills/${skill}" && ! -L "${repo_dir}/skills/${skill}" ]] \
        || err "Required skill unavailable: ${skill} (agent: ${agent_key})"
      linked_entry=$(find "${repo_dir}/skills/${skill}" -type l -print -quit)
      [[ -z "$linked_entry" ]] || err "Source skill contains a symlink: $linked_entry"
    done
  done
}

validate_install_paths() {
  local repo_dir="$1"
  shift
  local agent_key workspace destination_entry skill linked_entry

  if [[ -n "$repo_dir" && ( -e "$repo_dir" || -L "$repo_dir" ) && -L "$repo_dir" ]]; then
    err "Source path must not be a symlink: $repo_dir"
  fi
  if [[ ( -e "$OPENCLAW_DIR" || -L "$OPENCLAW_DIR" ) && -L "$OPENCLAW_DIR" ]]; then
    err "Destination path must not be a symlink: $OPENCLAW_DIR"
  fi
  if [[ -e "$OPENCLAW_DIR" && ! -d "$OPENCLAW_DIR" ]]; then
    err "Destination path must be a directory: $OPENCLAW_DIR"
  fi
  if [[ -e "${OPENCLAW_DIR}/agents" || -L "${OPENCLAW_DIR}/agents" ]]; then
    [[ -d "${OPENCLAW_DIR}/agents" && ! -L "${OPENCLAW_DIR}/agents" ]] \
      || err "Destination agents path must be a real directory: ${OPENCLAW_DIR}/agents"
    linked_entry=$(find "${OPENCLAW_DIR}/agents" -type l -print -quit)
    [[ -z "$linked_entry" ]] || err "Destination agents path contains a symlink: $linked_entry"
  fi
  for agent_key in "$@"; do
    workspace="${OPENCLAW_DIR}/workspace-${agent_key}"
    if [[ -e "$workspace" || -L "$workspace" ]]; then
      [[ -d "$workspace" && ! -L "$workspace" ]] \
        || err "Destination workspace must be a real directory: $workspace"
      linked_entry=$(find "$workspace" -type l -print -quit)
      [[ -z "$linked_entry" ]] || err "Destination workspace contains a symlink: $linked_entry"
    fi
    for destination_entry in skills SOUL.md AGENTS.md IDENTITY.md BOOTSTRAP.md MEMORY.md USER.md TOOLS.md WORKFLOW.md; do
      destination_entry="${workspace}/${destination_entry}"
      [[ ! -L "$destination_entry" ]] \
        || err "Destination entry must not be a symlink: $destination_entry"
    done
    for skill in $(agent_skills "$agent_key") $(agent_optional_skills "$agent_key"); do
      destination_entry="${workspace}/skills/${skill}"
      [[ ! -L "$destination_entry" ]] \
        || err "Destination skill must not be a symlink: $destination_entry"
    done
  done
}

copy_file_no_clobber() {
  local source_file="$1"
  local destination_dir="$2"
  local destination_file="${destination_dir}/$(basename "$source_file")"
  if [[ -L "$source_file" ]]; then
    err "Source file must not be a symlink: ${source_file}"
  elif [[ -L "$destination_file" ]]; then
    err "Destination file must not be a symlink: ${destination_file}"
  elif [[ -e "$destination_file" ]]; then
    warn "Preserved existing file: ${destination_file}"
  elif [[ "$(basename "$source_file")" == "TOOLS.md" ]]; then
    sed 's#\.\./\.\./skills/#skills/#g' "$source_file" > "$destination_file"
  else
    cp "$source_file" "$destination_file"
  fi
}

copy_skill_no_clobber() {
  local source_dir="$1"
  local destination_dir="$2"
  local destination_skill="${destination_dir}/$(basename "$source_dir")"
  if [[ -L "$source_dir" ]]; then
    err "Source skill must not be a symlink: ${source_dir}"
  elif [[ -L "$destination_skill" ]]; then
    err "Destination skill must not be a symlink: ${destination_skill}"
  elif [[ -e "$destination_skill" ]]; then
    warn "Preserved existing skill: ${destination_skill}"
  else
    cp -r "$source_dir" "$destination_dir/"
  fi
}

cleanup_stage() {
  if [[ -n "$INSTALL_STAGE" && -d "$INSTALL_STAGE" ]]; then
    rm -rf -- "$INSTALL_STAGE"
  fi
}

prepare_stage() {
  local destination_parent
  local agent_key final_workspace

  destination_parent=$(dirname "$OPENCLAW_DIR")
  [[ -d "$destination_parent" && ! -L "$destination_parent" ]] \
    || err "Destination parent must be an existing real directory: $destination_parent"

  INSTALL_STAGE=$(mktemp -d "${destination_parent}/.agi-super-team-stage.XXXXXX")
  DEPLOY_ROOT="${INSTALL_STAGE}/destination"
  mkdir -p "${DEPLOY_ROOT}/agents"
  trap cleanup_stage EXIT HUP INT TERM

  if [[ -d "$OPENCLAW_DIR" ]]; then
    if [[ -e "${OPENCLAW_DIR}/agents" || -L "${OPENCLAW_DIR}/agents" ]]; then
      [[ -d "${OPENCLAW_DIR}/agents" && ! -L "${OPENCLAW_DIR}/agents" ]] \
        || err "Destination agents path must be a real directory: ${OPENCLAW_DIR}/agents"
      rm -rf -- "${DEPLOY_ROOT}/agents"
      cp -R "${OPENCLAW_DIR}/agents" "${DEPLOY_ROOT}/agents"
    fi

    for agent_key in "$@"; do
      final_workspace="${OPENCLAW_DIR}/workspace-${agent_key}"
      if [[ -e "$final_workspace" || -L "$final_workspace" ]]; then
        [[ -d "$final_workspace" && ! -L "$final_workspace" ]] \
          || err "Destination workspace must be a real directory: $final_workspace"
        cp -R "$final_workspace" "${DEPLOY_ROOT}/workspace-${agent_key}"
      fi
    done
  fi
}

publish_stage() {
  local agent_key component staged_component final_component backup_component
  local -a components=(agents)
  local -a published=()
  local index published_component published_final published_backup
  for agent_key in "$@"; do
    components+=("workspace-${agent_key}")
  done

  if [[ ! -e "$OPENCLAW_DIR" && ! -L "$OPENCLAW_DIR" ]]; then
    mv "${DEPLOY_ROOT}" "$OPENCLAW_DIR"
    rmdir "$INSTALL_STAGE"
    INSTALL_STAGE=""
    trap - EXIT HUP INT TERM
    return
  fi

  mkdir -p "${INSTALL_STAGE}/backup"
  for component in "${components[@]}"; do
    staged_component="${DEPLOY_ROOT}/${component}"
    final_component="${OPENCLAW_DIR}/${component}"
    backup_component="${INSTALL_STAGE}/backup/${component}"
    if [[ -e "$final_component" || -L "$final_component" ]]; then
      if ! mv "$final_component" "$backup_component"; then
        for ((index=${#published[@]} - 1; index >= 0; index--)); do
          published_component="${published[$index]}"
          published_final="${OPENCLAW_DIR}/${published_component}"
          published_backup="${INSTALL_STAGE}/backup/${published_component}"
          rm -rf -- "$published_final"
          if [[ -e "$published_backup" || -L "$published_backup" ]]; then
            mv "$published_backup" "$published_final" || true
          fi
        done
        err "Atomic publish failed; restored the previous destination state"
      fi
    fi
    if ! mv "$staged_component" "$final_component"; then
      if [[ -e "$backup_component" || -L "$backup_component" ]]; then
        mv "$backup_component" "$final_component" || true
      fi
      for ((index=${#published[@]} - 1; index >= 0; index--)); do
        published_component="${published[$index]}"
        published_final="${OPENCLAW_DIR}/${published_component}"
        published_backup="${INSTALL_STAGE}/backup/${published_component}"
        rm -rf -- "$published_final"
        if [[ -e "$published_backup" || -L "$published_backup" ]]; then
          mv "$published_backup" "$published_final" || true
        fi
      done
      err "Atomic publish failed; restored the previous destination state"
    fi
    published+=("$component")
  done

  cleanup_stage
  INSTALL_STAGE=""
  trap - EXIT HUP INT TERM
}

# ── Deploy a single agent ─────────────────────────────────────
deploy_agent() {
  local repo_dir="$1"
  local agent_key="$2"   # e.g. "ceo", "pe", "cco"
  local ws="${DEPLOY_ROOT}/workspace-${agent_key}"

  local display_name
  display_name=$(agent_name "$agent_key")
  local src="${repo_dir}/$(agent_source_path "$agent_key")"
  local skill_list optional_skill_list skill

  if [[ -n "$repo_dir" ]]; then
    [[ -d "$src" ]] || err "Agent source not found: $src"
    skill_list=$(agent_skills "$agent_key")
    optional_skill_list=$(agent_optional_skills "$agent_key")

    for skill in $skill_list; do
      [[ -d "${repo_dir}/skills/${skill}" ]] \
        || err "Required skill unavailable: ${skill} (agent: ${agent_key})"
    done
  fi

  if [[ "$APPLY" -eq 0 ]]; then
    info "[PREVIEW] Would deploy ${display_name} → ${ws}"
    return
  fi

  info "Deploying ${display_name}..."

  # Create workspace
  mkdir -p "${ws}/skills" "${ws}/memory"

  # Copy persona files
  for f in SOUL.md AGENTS.md IDENTITY.md BOOTSTRAP.md MEMORY.md USER.md TOOLS.md WORKFLOW.md; do
    [[ -f "${src}/${f}" ]] && copy_file_no_clobber "${src}/${f}" "${ws}"
  done

  # Copy curated skills
  if [[ -n "$skill_list" ]]; then
    for skill in $skill_list; do
      copy_skill_no_clobber "${repo_dir}/skills/${skill}" "${ws}/skills"
    done
  fi

  if [[ -n "$optional_skill_list" ]]; then
    for skill in $optional_skill_list; do
      [[ -d "${repo_dir}/skills/${skill}" ]] && \
        copy_skill_no_clobber "${repo_dir}/skills/${skill}" "${ws}/skills"
    done
  fi

  # Copy shared docs
  for f in CHARTER.md COLLABORATION.md; do
    [[ -f "${repo_dir}/${f}" ]] && copy_file_no_clobber "${repo_dir}/${f}" "${DEPLOY_ROOT}/agents"
  done

  ok "Deployed ${display_name} → ${OPENCLAW_DIR}/workspace-${agent_key}"
}

# ── Starter Kits ──────────────────────────────────────────────
deploy_starter_kit() {
  local repo_dir="$1"
  local kit="$2"
  local filter="${3:-}"   # optional: deploy only one agent from kit

  local -a agents=()

  if [[ -n "$MANIFEST_PATH" ]]; then
    if [[ "$(manifest_query kit-exists "$kit")" == "yes" ]]; then
      while IFS= read -r a; do
        [[ -n "$a" ]] && agents+=("$a")
      done < <(manifest_query kit-agents "$kit")
    elif [[ "$(manifest_query agent-exists "$kit")" == "yes" ]]; then
      agents=("$kit")
    else
      err "Agent source not found: ${repo_dir}/agents/${kit}"
    fi
  else
    case "$kit" in
      solo-founder) agents=(ceo pe cco) ;;
      content-creator) agents=(cco cdo cmo) ;;
      quant-trader) agents=(cqo cdo cfo) ;;
      full-team) agents=(ceo cto pe cpo cqo cmo cfo cdo cco clo cro cso coo governor) ;;
      *)
        local resolved
        resolved=$(resolve_agent "$kit")
        agents=("$resolved")
        ;;
    esac
  fi

  # Filter to single agent if specified
  if [[ -n "$filter" ]]; then
    local resolved
    resolved=$(resolve_agent "$filter")
    local found=0
    for a in "${agents[@]}"; do
      [[ "$a" == "$resolved" ]] && found=1
    done
    [[ "$found" -eq 1 ]] || err "Agent '$filter' not found in kit '$kit'"
    agents=("$resolved")
  fi

  info "Deploying kit: ${kit} (${#agents[@]} agent(s))"

  validate_install_paths "$repo_dir" "${agents[@]}"
  preflight_agents "$repo_dir" "${agents[@]}"
  report_recommended_external_skills "${agents[@]}"
  if [[ "$APPLY" -eq 1 ]]; then
    prepare_stage "${agents[@]}"
  else
    DEPLOY_ROOT="$OPENCLAW_DIR"
  fi

  for a in "${agents[@]}"; do
    deploy_agent "$repo_dir" "$a"
  done

  if [[ "$APPLY" -eq 1 ]]; then
    publish_stage "${agents[@]}"
  fi

  echo ""
  ok "════════════════════════════════════════"
  if [[ "$APPLY" -eq 1 ]]; then
    ok " Kit '${kit}' deployed! ${#agents[@]} agent(s) ready"
  else
    ok " PREVIEW complete for '${kit}': ${#agents[@]} agent(s)"
    info "Re-run with --apply to perform these writes."
  fi
  ok "════════════════════════════════════════"
  echo ""
  echo "Next steps:"
  echo "  Recommended (harness-native, no extra tooling):"
  echo "    Claude Code:  /plugin install aAAaqwq/AGI-Super-Team"
  echo "    Or open ~/.openclaw/workspace-<agent>/ in your harness (Claude Code / Codex / Cursor / Hermes)"
  echo "  (legacy, only if using the discontinued OpenClaw harness):"
  echo "    1. Configure your API keys:  openclaw config"
  echo "    2. Restart the gateway:       openclaw gateway restart"
  echo "  Then start chatting with your agent!"
  echo ""
  if [[ "$APPLY" -eq 1 ]]; then
    echo "Deployed agents:"
  else
    echo "Planned agents:"
  fi
  for a in "${agents[@]}"; do
    echo "  • $(agent_name "$a") → ${OPENCLAW_DIR}/workspace-${a}/"
  done
}

# ── Main ──────────────────────────────────────────────────────
main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --source) [[ $# -ge 2 ]] || err "--source requires a path"; SOURCE_DIR="$2"; shift 2 ;;
      --destination) [[ $# -ge 2 ]] || err "--destination requires a path"; OPENCLAW_DIR="$2"; shift 2 ;;
      --apply) APPLY=1; shift ;;
      --) shift; break ;;
      -*) err "Unknown option: $1" ;;
      *) break ;;
    esac
  done

  echo ""
  echo "╔══════════════════════════════════════╗"
  echo "║     🏛️  AGI Super Team Deployer      ║"
  echo "║     794 Skills : 14 Agents            ║"
  echo "╚══════════════════════════════════════╝"
  echo ""

  check_prereqs

  local kit="${1:-solo-founder}"
  local agent_filter="${2:-}"

  local repo_dir
  ensure_repo
  repo_dir="$RETVAL_REPO"
  load_team_manifest "$repo_dir"

  deploy_starter_kit "$repo_dir" "$kit" "$agent_filter"
}

main "$@"
