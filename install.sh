#!/usr/bin/env bash
# AGI Super Team — Generic Workspace Materializer
# Usage: ./install.sh --source PATH [--destination PATH] [--apply] (--kit ID | --agent ID)
#
# Examples:
#   ./install.sh --source "$PWD" --kit solo-founder
#   ./install.sh --source "$PWD" --layout coordinated --kit full-team
#   ./install.sh --source "$PWD" --apply --agent ceo
#
# Review a trusted checkout before running this script. It materializes portable
# role workspaces; the chosen harness still owns models, tools, credentials,
# delegation, and runtime verification.
#
set -euo pipefail

REPO_URL="https://github.com/aAAaqwq/AGI-Super-Team.git"
REPO_REF="${AGI_SUPER_TEAM_REF:-v1.4.1}"
OPENCLAW_DIR="${AGI_SUPER_TEAM_DESTINATION:-${HOME}/.openclaw}"
SOURCE_DIR="${AGI_SUPER_TEAM_SOURCE:-}"
APPLY=0
SKILL_TIER="standard"
TEAM_TIER="full"
LAYOUT="isolated"
SELECTOR_KIND=""
MANIFEST_PATH=""
DEPLOY_ROOT=""
INSTALL_STAGE=""
INSTALL_LOCK=""
TRANSACTION_ACTIVE=0
TRANSACTION_SIGNAL=""
TRANSACTION_ROOT_MOVE=0
TRANSACTION_ROOT_TOKEN=""
declare -a TRANSACTION_COMPONENTS=()
declare -a TRANSACTION_ORIGINAL_PRESENT=()
declare -a TRANSACTION_ORIGINAL_DIGESTS=()
declare -a TRANSACTION_STAGED_DIGESTS=()
SNAPSHOT_DESTINATION_PRESENT=0
declare -a SNAPSHOT_COMPONENTS=()
declare -a SNAPSHOT_DIGESTS=()

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
  info "Prerequisites ✓"
}

# ── Clone or update repo ──────────────────────────────────────
validate_repo_ref() {
  [[ "$REPO_REF" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ \
     && "$REPO_REF" != *..* && "$REPO_REF" != */./* \
     && "$REPO_REF" != */. && "$REPO_REF" != *.lock ]] \
    || err "Invalid repository ref: $REPO_REF"
}

checkout_pinned_ref() {
  local repo_dir="$1" commit="$2" actual
  if ! git -C "$repo_dir" checkout --detach --quiet "$commit"; then
    err "Unable to check out pinned repository ref: $REPO_REF"
  fi
  if ! actual=$(git -C "$repo_dir" rev-parse --verify HEAD 2>/dev/null); then
    err "Unable to verify checked-out repository ref: $REPO_REF"
  fi
  [[ "$actual" == "$commit" ]] \
    || err "Checked-out repository does not match pinned ref: $REPO_REF"
}

ensure_repo() {
  local clone_dir="${1:-${HOME}/.agi-super-team}"
  local clone_parent clone_stage="" status commit

  if [[ -n "$SOURCE_DIR" ]]; then
    [[ -d "$SOURCE_DIR/agents" && -d "$SOURCE_DIR/skills" ]] \
      || err "Local source is not an AGI Super Team checkout: $SOURCE_DIR"
    RETVAL_REPO="$SOURCE_DIR"
    return
  fi

  validate_repo_ref
  if [[ "$APPLY" -eq 0 ]]; then
    info "[PREVIEW] Would resolve ${REPO_URL} at pinned ref ${REPO_REF} into ${HOME}/.agi-super-team"
    RETVAL_REPO=""
    return
  fi

  if [[ -d "$clone_dir/.git" ]]; then
    info "Resolving pinned repository ref ${REPO_REF} in $clone_dir"
    if ! status=$(git -C "$clone_dir" status --porcelain --untracked-files=all 2>/dev/null); then
      err "Unable to inspect cached repository before switching refs: $clone_dir"
    fi
    [[ -z "$status" ]] \
      || err "Cached repository has local changes; refusing to switch refs: $clone_dir"
    if ! git -C "$clone_dir" fetch --depth 1 "$REPO_URL" "$REPO_REF"; then
      err "Unable to fetch pinned repository ref: $REPO_REF"
    fi
    if ! commit=$(git -C "$clone_dir" rev-parse --verify 'FETCH_HEAD^{commit}' 2>/dev/null); then
      err "Unable to resolve pinned repository ref: $REPO_REF"
    fi
    checkout_pinned_ref "$clone_dir" "$commit"
  else
    [[ ! -e "$clone_dir" && ! -L "$clone_dir" ]] \
      || err "Repository cache path exists but is not a Git checkout: $clone_dir"
    clone_parent=$(dirname "$clone_dir")
    mkdir -p "$clone_parent"
    clone_stage=$(mktemp -d "${clone_parent}/.agi-super-team-source.XXXXXX")
    rmdir "$clone_stage"
    info "Cloning AGI Super Team at pinned ref ${REPO_REF}..."
    if ! git clone --no-checkout --depth 1 --branch "$REPO_REF" "$REPO_URL" "$clone_stage" -q; then
      rm -rf -- "$clone_stage"
      err "Unable to clone pinned repository ref: $REPO_REF"
    fi
    if ! commit=$(git -C "$clone_stage" rev-parse --verify "${REPO_REF}^{commit}" 2>/dev/null); then
      rm -rf -- "$clone_stage"
      err "Unable to resolve pinned repository ref: $REPO_REF"
    fi
    if ! git -C "$clone_stage" checkout --detach --quiet "$commit"; then
      rm -rf -- "$clone_stage"
      err "Unable to check out pinned repository ref: $REPO_REF"
    fi
    if ! status=$(git -C "$clone_stage" rev-parse --verify HEAD 2>/dev/null); then
      rm -rf -- "$clone_stage"
      err "Unable to verify checked-out repository ref: $REPO_REF"
    fi
    if [[ "$status" != "$commit" ]]; then
      rm -rf -- "$clone_stage"
      err "Checked-out repository does not match pinned ref: $REPO_REF"
    fi
    if ! mv "$clone_stage" "$clone_dir"; then
      rm -rf -- "$clone_stage"
      err "Unable to publish pinned repository checkout: $clone_dir"
    fi
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
  case 'harnessSpecific':
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
  case 'kit-core-agents':
    if (!kit) process.exit(2);
    process.stdout.write((kit.coreAgents || kit.agents).map(String).join('\n'));
    if ((kit.coreAgents || kit.agents).length) process.stdout.write('\n');
    break;
  case 'kit-coordinator':
    if (!kit) process.exit(2);
    process.stdout.write(`${kit.coordinator || (kit.agents.includes('ceo') ? 'ceo' : kit.agents[0])}\n`);
    break;
  case 'kit-reviewers': {
    if (!kit) process.exit(2);
    const reviewers = kit.reviewers || (kit.agents.includes('governor') ? ['governor'] : []);
    process.stdout.write(reviewers.map(String).join('\n'));
    if (reviewers.length) process.stdout.write('\n');
    break;
  }
  case 'kit-entrypoint':
    if (!kit) process.exit(2);
    process.stdout.write(`${kit.entrypoint}\n`);
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
    if ! node - "$MANIFEST_PATH" <<'NODE'
const fs = require('fs');
const manifestPath = process.argv[2];
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const identifier = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const exactKeys = (value, expected) => value && typeof value === 'object'
  && !Array.isArray(value)
  && Object.keys(value).sort().join('\0') === [...expected].sort().join('\0');
const validIds = value => Array.isArray(value)
  && value.every(item => typeof item === 'string' && identifier.test(item))
  && new Set(value).size === value.length;
const descriptiveText = value => typeof value === 'string' && value.trim().length >= 24;
const validOutputs = value => Array.isArray(value)
  && value.length >= 2 && value.length <= 5
  && value.every(item => typeof item === 'string' && item.trim().length >= 3)
  && new Set(value).size === value.length;
const validKitOutputs = value => Array.isArray(value)
  && value.length >= 2 && value.length <= 6
  && value.every(item => typeof item === 'string' && item.trim().length >= 3)
  && new Set(value).size === value.length;
if (manifest.$schema !== './team-manifest.schema.json' || manifest.schemaVersion !== 1) process.exit(1);
if (!exactKeys(manifest, ['$schema', 'schemaVersion', 'inventory', 'agents', 'kits'])) process.exit(1);
if (!Array.isArray(manifest.agents) || !Array.isArray(manifest.kits)
    || !manifest.agents.length || !manifest.kits.length) process.exit(1);
if (!exactKeys(manifest.inventory, ['agentCount', 'physicalSkillCount', 'skillEntrypoint', 'symlinkPolicy'])) process.exit(1);
if (!Number.isInteger(manifest.inventory.agentCount) || manifest.inventory.agentCount < 1
    || manifest.inventory.agentCount !== manifest.agents.length
    || !Number.isInteger(manifest.inventory.physicalSkillCount)
    || manifest.inventory.physicalSkillCount < 0
    || manifest.inventory.skillEntrypoint !== 'SKILL.md'
    || manifest.inventory.symlinkPolicy !== 'forbid') process.exit(1);
const agentIds = manifest.agents.map(agent => agent && agent.id);
if (!validIds(agentIds)) process.exit(1);
const knownAgents = new Set(agentIds);
for (const agent of manifest.agents) {
  if (!exactKeys(agent, ['id', 'name', 'path', 'focus', 'outputs', 'boundary', 'skills'])) process.exit(1);
  if (typeof agent.name !== 'string' || !agent.name.trim()) process.exit(1);
  if (!descriptiveText(agent.focus) || !descriptiveText(agent.boundary)
      || !validOutputs(agent.outputs)) process.exit(1);
  if (agent.path !== `agents/${agent.id}`) process.exit(1);
  if (!exactKeys(agent.skills, ['required', 'optional', 'harnessSpecific', 'recommendedExternal'])) process.exit(1);
  if (!agent.skills || !validIds(agent.skills.required) || !validIds(agent.skills.optional)
      || !validIds(agent.skills.harnessSpecific)
      || !validIds(agent.skills.recommendedExternal)) process.exit(1);
  const allSkills = [
    ...agent.skills.required,
    ...agent.skills.optional,
    ...agent.skills.harnessSpecific,
    ...agent.skills.recommendedExternal,
  ];
  if (new Set(allSkills).size !== allSkills.length) process.exit(1);
}
const kitIds = manifest.kits.map(kit => kit && kit.id);
if (!validIds(kitIds)) process.exit(1);
for (const kit of manifest.kits) {
  const layeredKit = exactKeys(kit, [
    'id', 'name', 'outcome', 'entrypoint', 'coordinator', 'reviewers',
    'coreAgents', 'agents', 'outputs', 'checks',
  ]);
  if (!layeredKit) process.exit(1);
  if (!validIds(kit.agents) || kit.agents.length < 3
      || kit.agents.some(agent => !knownAgents.has(agent))) process.exit(1);
  if (typeof kit.name !== 'string' || kit.name.trim().length < 3
      || !descriptiveText(kit.outcome)
      || typeof kit.entrypoint !== 'string'
      || !/^starter-kits\/[a-z0-9]+(?:-[a-z0-9]+)*\/RUNBOOK\.md$/.test(kit.entrypoint)
      || !knownAgents.has(kit.coordinator)
      || !validIds(kit.reviewers) || !kit.reviewers.length
      || kit.reviewers.some(agent => !knownAgents.has(agent))
      || kit.reviewers.includes(kit.coordinator)
      || !validIds(kit.coreAgents) || kit.coreAgents.length < 2
      || kit.coreAgents.some(agent => !kit.agents.includes(agent))
      || !kit.coreAgents.includes(kit.coordinator)
      || kit.reviewers.some(agent => !kit.coreAgents.includes(agent))
      || !validKitOutputs(kit.outputs)
      || !validIds(kit.checks) || kit.checks.length < 2) process.exit(1);
  if (kit.id === 'full-team') {
    const fullRoster = new Set(kit.agents);
    if (kit.agents.length !== 14 || kit.coordinator !== 'ceo'
        || !kit.reviewers.includes('governor')
        || agentIds.some(agent => !fullRoster.has(agent))) process.exit(1);
  }
}
NODE
    then
      err "Invalid team manifest: $MANIFEST_PATH"
    fi
    info "Using team manifest: $MANIFEST_PATH"
  elif [[ -n "$repo_dir" ]]; then
    err "Required team manifest unavailable: $candidate"
  fi
}

agent_name() {
  [[ -n "$MANIFEST_PATH" ]] || err "Canonical team manifest is not loaded"
  manifest_query agent-name "$1"
}

# ── Skills for each agent (curated top skills) ────────────────
agent_skills() {
  if [[ "$SKILL_TIER" == "role-only" ]]; then
    printf '\n'
    return
  fi
  [[ -n "$MANIFEST_PATH" ]] || err "Canonical team manifest is not loaded"
  manifest_query required "$1"
}

agent_recommended_external_skills() {
  [[ -n "$MANIFEST_PATH" ]] || err "Canonical team manifest is not loaded"
  manifest_query recommendedExternal "$1"
}

agent_optional_skills() {
  if [[ "$SKILL_TIER" != "standard" ]]; then
    printf '\n'
    return
  fi
  if [[ -n "$MANIFEST_PATH" ]]; then
    manifest_query optional "$1"
  else
    err "Canonical team manifest is not loaded"
  fi
}

agent_harness_specific_skills() {
  if [[ -n "$MANIFEST_PATH" ]]; then
    manifest_query harnessSpecific "$1"
  else
    err "Canonical team manifest is not loaded"
  fi
}

agent_source_path() {
  if [[ -n "$MANIFEST_PATH" ]]; then
    manifest_query agent-path "$1"
  else
    err "Canonical team manifest is not loaded"
  fi
}

report_recommended_external_skills() {
  local agent_key skill count=0 harness_count=0
  for agent_key in "$@"; do
    for skill in $(agent_recommended_external_skills "$agent_key"); do
      count=$((count + 1))
    done
    for skill in $(agent_harness_specific_skills "$agent_key"); do
      harness_count=$((harness_count + 1))
    done
  done
  if [[ "$count" -gt 0 ]]; then
    info "${count} recommended external skill(s) are not bundled; see the team manifest for details."
  fi
  if [[ "$harness_count" -gt 0 ]]; then
    info "${harness_count} harness-specific skill assignment(s) stay catalog-only and are not copied by the generic installer."
  fi
}

preflight_kit_entrypoint() {
  local repo_dir="$1"
  local kit="$2"
  local entrypoint source_file

  [[ "$(manifest_query kit-exists "$kit")" == "yes" ]] || return 0
  entrypoint=$(manifest_query kit-entrypoint "$kit")
  source_file="${repo_dir}/${entrypoint}"
  [[ ( -e "$source_file" || -L "$source_file" ) && -f "$source_file" && ! -L "$source_file" ]] \
    || err "Kit entrypoint must be a real regular file: $source_file"
}

preflight_agents() {
  local repo_dir="$1"
  shift
  local agent_key src skill skill_list optional_skill_list source_name source_file linked_entry

  [[ -n "$repo_dir" ]] || return 0
  for source_name in CHARTER.md COLLABORATION.md agents/BOOTSTRAP.md agents/WORKFLOW.md; do
    source_file="${repo_dir}/${source_name}"
    [[ ( -e "$source_file" || -L "$source_file" ) && -f "$source_file" && ! -L "$source_file" ]] \
      || err "Required shared workspace file unavailable: $source_name"
  done
  for agent_key in "$@"; do
    src="${repo_dir}/$(agent_source_path "$agent_key")"
    [[ ( -e "$src" || -L "$src" ) && -d "$src" && ! -L "$src" ]] \
      || err "Agent source must be a real directory: $src"
    for source_name in SOUL.md AGENTS.md IDENTITY.md USER.md TOOLS.md; do
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
    for destination_entry in skills SOUL.md AGENTS.md IDENTITY.md BOOTSTRAP.md USER.md TOOLS.md WORKFLOW.md; do
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

  if [[ "$LAYOUT" == "coordinated" && -d "$OPENCLAW_DIR" ]]; then
    for destination_entry in AGENTS.md START_HERE.md TEAM.md RUNBOOK.md team.lock.json; do
      destination_entry="${OPENCLAW_DIR}/${destination_entry}"
      [[ -e "$destination_entry" || -L "$destination_entry" ]] || continue
      [[ -f "$destination_entry" && ! -L "$destination_entry" ]] \
        || err "Destination team contract must be a regular non-symlink file: $destination_entry"
      if [[ "$(basename "$destination_entry")" == "team.lock.json" ]]; then
        node - "$destination_entry" <<'NODE' \
          || err "Destination team contract is not installer-managed: $destination_entry"
const fs = require('fs');
const value = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
if (value.managedBy !== 'agi-super-team-installer') process.exit(1);
NODE
      else
        IFS= read -r linked_entry < "$destination_entry" || true
        [[ "$linked_entry" == '<!-- managed-by: agi-super-team-installer -->' ]] \
          || err "Destination team contract is not installer-managed: $destination_entry"
      fi
    done
  fi
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

write_manifest_tools_no_clobber() {
  local destination_dir="$1"
  local agent_key="$2"
  local destination_file="${destination_dir}/TOOLS.md"
  local skill
  if [[ -L "$destination_file" ]]; then
    err "Destination file must not be a symlink: ${destination_file}"
  elif [[ -e "$destination_file" ]]; then
    warn "Preserved existing file: ${destination_file}"
    return
  fi
  {
    printf '# Skill assignment\n\n'
    printf 'Generated from the canonical team manifest for `%s`. This list contains only portable Skills copied by the generic installer.\n\n' "$agent_key"
    printf '## Required\n\n'
    for skill in $(agent_skills "$agent_key"); do
      printf -- '- [`%s`](skills/%s/)\n' "$skill" "$skill"
    done
    if [[ -n "$(agent_optional_skills "$agent_key")" ]]; then
      printf '\n## Optional\n\n'
      for skill in $(agent_optional_skills "$agent_key"); do
        printf -- '- [`%s`](skills/%s/)\n' "$skill" "$skill"
      done
    fi
  } > "$destination_file"
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

release_destination_lock() {
  local owner=""
  [[ -n "$INSTALL_LOCK" ]] || return 0
  if [[ -d "$INSTALL_LOCK" && ! -L "$INSTALL_LOCK" ]]; then
    if [[ -f "${INSTALL_LOCK}/pid" ]]; then
      IFS= read -r owner < "${INSTALL_LOCK}/pid" || true
    fi
    if [[ "$owner" == "$$" ]]; then
      rm -f -- "${INSTALL_LOCK}/pid" "${INSTALL_LOCK}/destination"
      rmdir "$INSTALL_LOCK" 2>/dev/null || warn "Installer lock could not be removed: $INSTALL_LOCK"
    else
      warn "Installer lock ownership changed; left it in place: $INSTALL_LOCK"
    fi
  fi
  INSTALL_LOCK=""
}

acquire_destination_lock() {
  local destination_parent destination_name physical_parent
  destination_parent=$(dirname "$OPENCLAW_DIR")
  destination_name=$(basename "$OPENCLAW_DIR")
  [[ -d "$destination_parent" && ! -L "$destination_parent" ]] \
    || err "Destination parent must be an existing real directory: $destination_parent"
  physical_parent=$(CDPATH= cd -- "$destination_parent" && pwd -P) \
    || err "Unable to resolve destination parent: $destination_parent"
  INSTALL_LOCK="${physical_parent}/.${destination_name}.agi-super-team-install.lock"
  if ! mkdir "$INSTALL_LOCK" 2>/dev/null; then
    INSTALL_LOCK=""
    err "Another installation is active for destination: $OPENCLAW_DIR"
  fi
  printf '%s\n' "$$" > "${INSTALL_LOCK}/pid"
  printf '%s\n' "$OPENCLAW_DIR" > "${INSTALL_LOCK}/destination"
  trap transaction_on_exit EXIT
  trap 'transaction_on_signal HUP' HUP
  trap 'transaction_on_signal INT' INT
  trap 'transaction_on_signal TERM' TERM
}

fingerprint_path() {
  node - "$1" <<'NODE'
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const root = process.argv[2];
const hash = crypto.createHash('sha256');
const visit = (entry, relative = '') => {
  const stat = fs.lstatSync(entry);
  const kind = stat.isDirectory() ? 'd' : stat.isFile() ? 'f' : stat.isSymbolicLink() ? 'l' : 'o';
  hash.update(`${kind}\0${relative}\0${stat.mode & 0o777}\0`);
  if (stat.isDirectory()) {
    for (const name of fs.readdirSync(entry).sort()) visit(path.join(entry, name), path.join(relative, name));
  } else if (stat.isFile()) {
    hash.update(fs.readFileSync(entry));
  } else if (stat.isSymbolicLink()) {
    hash.update(fs.readlinkSync(entry));
  }
};
let rootStat;
try {
  rootStat = fs.lstatSync(root);
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
if (!rootStat) {
  process.stdout.write('absent\n');
} else {
  visit(root);
  process.stdout.write(`${hash.digest('hex')}\n`);
}
NODE
}

snapshot_destination_state() {
  local agent_key component digest
  local -a components=(agents)
  for agent_key in "$@"; do
    components+=("workspace-${agent_key}")
  done
  if [[ "$LAYOUT" == "coordinated" ]]; then
    components+=(AGENTS.md START_HERE.md TEAM.md RUNBOOK.md team.lock.json)
  fi

  SNAPSHOT_DESTINATION_PRESENT=0
  SNAPSHOT_COMPONENTS=()
  SNAPSHOT_DIGESTS=()
  if [[ -e "$OPENCLAW_DIR" || -L "$OPENCLAW_DIR" ]]; then
    SNAPSHOT_DESTINATION_PRESENT=1
  fi
  for component in "${components[@]}"; do
    digest=$(fingerprint_path "${OPENCLAW_DIR}/${component}") \
      || err "Unable to snapshot destination component: ${OPENCLAW_DIR}/${component}"
    SNAPSHOT_COMPONENTS+=("$component")
    SNAPSHOT_DIGESTS+=("$digest")
  done
}

verify_destination_snapshot() {
  local index component expected actual destination_present=0
  if [[ -e "$OPENCLAW_DIR" || -L "$OPENCLAW_DIR" ]]; then
    destination_present=1
  fi
  if [[ "$destination_present" -ne "$SNAPSHOT_DESTINATION_PRESENT" ]]; then
    err "Destination changed after staging began: $OPENCLAW_DIR"
  fi
  for ((index=0; index < ${#SNAPSHOT_COMPONENTS[@]}; index++)); do
    component="${SNAPSHOT_COMPONENTS[$index]}"
    expected="${SNAPSHOT_DIGESTS[$index]}"
    actual=$(fingerprint_path "${OPENCLAW_DIR}/${component}") \
      || err "Unable to verify destination component: ${OPENCLAW_DIR}/${component}"
    if [[ "$actual" != "$expected" ]]; then
      err "Destination changed after staging began: ${OPENCLAW_DIR}/${component}"
    fi
  done
}

rollback_transaction() {
  local index component final_component backup_component original_present original_digest staged_digest current_digest marker recovery_destination
  local restore_failed=0

  if [[ "$TRANSACTION_ROOT_MOVE" -eq 1 ]]; then
    marker="${OPENCLAW_DIR}/.agi-super-team-transaction"
    if [[ -f "$marker" && ! -L "$marker" \
       && "$(<"$marker")" == "$TRANSACTION_ROOT_TOKEN" ]]; then
      recovery_destination="${INSTALL_STAGE}/recovery-destination"
      if [[ ! -e "$recovery_destination" && ! -L "$recovery_destination" ]]; then
        # A digest check cannot authorize recursive deletion: another writer
        # can add data after the check. Quarantine the entire root atomically
        # and require explicit recovery review instead.
        mv "$OPENCLAW_DIR" "$recovery_destination" || true
      fi
      restore_failed=1
    elif [[ -e "$OPENCLAW_DIR" || -L "$OPENCLAW_DIR" ]]; then
      restore_failed=1
    fi
  fi

  for ((index=${#TRANSACTION_COMPONENTS[@]} - 1; index >= 0; index--)); do
    component="${TRANSACTION_COMPONENTS[$index]}"
    original_present="${TRANSACTION_ORIGINAL_PRESENT[$index]}"
    original_digest="${TRANSACTION_ORIGINAL_DIGESTS[$index]}"
    staged_digest="${TRANSACTION_STAGED_DIGESTS[$index]}"
    final_component="${OPENCLAW_DIR}/${component}"
    backup_component="${INSTALL_STAGE}/backup/${component}"

    if [[ "$original_present" -eq 1 ]]; then
      if [[ -e "$backup_component" || -L "$backup_component" ]]; then
        if [[ -e "$final_component" || -L "$final_component" ]]; then
          current_digest=$(fingerprint_path "$final_component") || current_digest="unknown"
          if [[ "$current_digest" != "$staged_digest" ]]; then
            restore_failed=1
            continue
          fi
          rm -rf -- "$final_component" || { restore_failed=1; continue; }
        fi
        mv "$backup_component" "$final_component" || restore_failed=1
      else
        current_digest=$(fingerprint_path "$final_component") || current_digest="unknown"
        [[ "$current_digest" == "$original_digest" ]] || restore_failed=1
      fi
    elif [[ -e "$final_component" || -L "$final_component" ]]; then
      current_digest=$(fingerprint_path "$final_component") || current_digest="unknown"
      if [[ "$current_digest" == "$staged_digest" ]]; then
        rm -rf -- "$final_component" || restore_failed=1
      else
        restore_failed=1
      fi
    fi
  done

  return "$restore_failed"
}

transaction_on_exit() {
  local status="$?" recovery_path="" restored=1
  trap - EXIT HUP INT TERM
  if [[ "$TRANSACTION_ACTIVE" -eq 1 ]]; then
    rollback_transaction || restored=0
  fi
  if [[ "$restored" -eq 1 ]]; then
    cleanup_stage
    if [[ -n "$TRANSACTION_SIGNAL" ]]; then
      warn "Received ${TRANSACTION_SIGNAL}; restored the previous destination state"
    elif [[ "$status" -ne 0 && "${#TRANSACTION_COMPONENTS[@]}" -gt 0 ]]; then
      warn "Atomic publish failed; restored the previous destination state"
    fi
  else
    recovery_path="$INSTALL_STAGE"
    INSTALL_STAGE=""
    warn "automatic restore is incomplete. Recovery transaction preserved at: $recovery_path"
  fi
  release_destination_lock
  exit "$status"
}

transaction_on_signal() {
  TRANSACTION_SIGNAL="$1"
  case "$1" in
    HUP) exit 129 ;;
    INT) exit 130 ;;
    TERM) exit 143 ;;
  esac
}

move_transaction_path() {
  local status=0
  if mv "$@"; then
    return 0
  else
    status=$?
  fi
  case "$status" in
    129) TRANSACTION_SIGNAL=HUP; err "Atomic publish interrupted" ;;
    130) TRANSACTION_SIGNAL=INT; err "Atomic publish interrupted" ;;
    143) TRANSACTION_SIGNAL=TERM; err "Atomic publish interrupted" ;;
    *) err "Atomic publish failed" ;;
  esac
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
  TRANSACTION_ACTIVE=1
  TRANSACTION_SIGNAL=""
  TRANSACTION_ROOT_MOVE=0
  TRANSACTION_ROOT_TOKEN=""
  TRANSACTION_COMPONENTS=()
  TRANSACTION_ORIGINAL_PRESENT=()
  TRANSACTION_ORIGINAL_DIGESTS=()
  TRANSACTION_STAGED_DIGESTS=()
  trap transaction_on_exit EXIT
  trap 'transaction_on_signal HUP' HUP
  trap 'transaction_on_signal INT' INT
  trap 'transaction_on_signal TERM' TERM

  snapshot_destination_state "$@"

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

write_coordinated_team() {
  local repo_dir="$1"
  local kit="$2"
  shift 2
  local -a selected_agents=("$@")
  local coordinator="" reviewer agent_key role reviewers_text="" entrypoint source_runbook

  coordinator=$(manifest_query kit-coordinator "$kit")
  entrypoint=$(manifest_query kit-entrypoint "$kit")
  source_runbook="${repo_dir}/${entrypoint}"
  while IFS= read -r reviewer; do
    [[ -n "$reviewer" ]] || continue
    reviewers_text+="${reviewer} "
  done < <(manifest_query kit-reviewers "$kit")
  reviewers_text="${reviewers_text% }"

  cat > "${DEPLOY_ROOT}/AGENTS.md" <<'EOF'
<!-- managed-by: agi-super-team-installer -->
# Coordinated AGI Super Team

Read `RUNBOOK.md` first, then open `TEAM.md`, `START_HERE.md`, and the selected role workspaces before acting.

The CEO coordinator lives in `workspace-ceo`. It scopes the brief, assigns bounded specialist work, collects evidence, and sends the result to the configured reviewer.

First inspect whether the active harness exposes a real delegation capability. If it does, delegate with explicit objective, ownership, checks, and safety limits. If it does not, use sequential/manual handoffs between the listed workspaces. Never claim that a subagent was started without observable harness confirmation.

This directory is materialized content, not runtime-verified execution. External publishing, credentials, transactions, deployments, merges, and destructive actions require human approval.
EOF

  cat > "${DEPLOY_ROOT}/START_HERE.md" <<'EOF'
<!-- managed-by: agi-super-team-installer -->
# Start here

Open this destination root in your configured agent harness. Read `RUNBOOK.md` first, then ask it to read `AGENTS.md`, `TEAM.md`, `agents/CHARTER.md`, and `agents/COLLABORATION.md` before handling your brief.

The installed files do not prove that a harness loaded roles or started subagents. Require observable delegation results, specialist handoffs, reviewer evidence, and a human approval gate.
EOF

  {
      printf '<!-- managed-by: agi-super-team-installer -->\n'
      printf '# Materialized team\n\n'
      printf 'Selector: `%s` · Skill tier: `%s` · Team tier: `%s` · Runtime verification: **pending**\n\n' \
        "$kit" "$SKILL_TIER" "$TEAM_TIER"
      printf '| Function | Agent | Workspace |\n|---|---|---|\n'
      for agent_key in "${selected_agents[@]}"; do
        role="Specialist"
        [[ "$agent_key" == "$coordinator" ]] && role="Coordinator"
        if [[ " $reviewers_text " == *" $agent_key "* ]]; then role="Reviewer"; fi
        printf '| %s | %s | `workspace-%s` |\n' "$role" "$(agent_name "$agent_key")" "$agent_key"
      done
      printf '\nOnly the workspaces listed above belong to the current materialized plan. Unlisted workspace directories from an earlier install are preserved as unmanaged local data and are not active team members.\n\n'
      printf 'Use the routing and handoff contract in `agents/COLLABORATION.md`.\n'
  } > "${DEPLOY_ROOT}/TEAM.md"

  {
    printf '<!-- managed-by: agi-super-team-installer -->\n'
    cat "$source_runbook"
  } > "${DEPLOY_ROOT}/RUNBOOK.md"

  node - "${DEPLOY_ROOT}/team.lock.json" "$MANIFEST_PATH" "$kit" "$LAYOUT" "$SKILL_TIER" "$TEAM_TIER" \
    "$coordinator" "$reviewers_text" "${selected_agents[@]}" <<'NODE'
const crypto = require('crypto');
const fs = require('fs');
const [path, manifestPath, selector, layout, skillTier, teamTier, coordinator, reviewerText, ...agents] = process.argv.slice(2);
const manifestBytes = fs.readFileSync(manifestPath);
const manifest = JSON.parse(manifestBytes);
const kit = manifest.kits.find(item => item.id === selector);
if (!kit) process.exit(2);
fs.writeFileSync(path, `${JSON.stringify({
  schemaVersion: 1,
  managedBy: 'agi-super-team-installer',
  status: 'materialized',
  runtimeVerified: false,
  selector,
  layout,
  skillTier,
  teamTier,
  coordinator,
  reviewers: reviewerText.split(/\s+/).filter(Boolean),
  agents,
  entrypoint: kit.entrypoint,
  outputs: kit.outputs,
  checks: kit.checks,
  manifestDigest: crypto.createHash('sha256').update(manifestBytes).digest('hex'),
}, null, 2)}\n`);
NODE
}

publish_stage() {
  local agent_key component staged_component final_component backup_component
  local -a components=(agents)
  local original_present original_digest staged_digest
  for agent_key in "$@"; do
    components+=("workspace-${agent_key}")
  done
  if [[ "$LAYOUT" == "coordinated" ]]; then
    components+=(AGENTS.md START_HERE.md TEAM.md RUNBOOK.md team.lock.json)
  fi

  verify_destination_snapshot

  if [[ ! -e "$OPENCLAW_DIR" && ! -L "$OPENCLAW_DIR" ]]; then
    TRANSACTION_ROOT_TOKEN=$(node -e "process.stdout.write(require('crypto').randomBytes(32).toString('hex'))") \
      || err "Unable to create a transaction identifier"
    printf '%s\n' "$TRANSACTION_ROOT_TOKEN" > "${DEPLOY_ROOT}/.agi-super-team-transaction"
    TRANSACTION_ROOT_MOVE=1
    move_transaction_path "${DEPLOY_ROOT}" "$OPENCLAW_DIR"
    rm -f -- "${OPENCLAW_DIR}/.agi-super-team-transaction"
    TRANSACTION_ROOT_MOVE=0
    TRANSACTION_ACTIVE=0
    rmdir "$INSTALL_STAGE"
    INSTALL_STAGE=""
    release_destination_lock
    trap - EXIT HUP INT TERM
    return
  fi

  mkdir -p "${INSTALL_STAGE}/backup"
  for component in "${components[@]}"; do
    staged_component="${DEPLOY_ROOT}/${component}"
    final_component="${OPENCLAW_DIR}/${component}"
    backup_component="${INSTALL_STAGE}/backup/${component}"
    original_present=0
    if [[ -e "$final_component" || -L "$final_component" ]]; then
      original_present=1
    fi
    original_digest=$(fingerprint_path "$final_component") \
      || err "Unable to fingerprint destination component: $final_component"
    staged_digest=$(fingerprint_path "$staged_component") || err "Unable to fingerprint staged component: $staged_component"
    TRANSACTION_COMPONENTS+=("$component")
    TRANSACTION_ORIGINAL_PRESENT+=("$original_present")
    TRANSACTION_ORIGINAL_DIGESTS+=("$original_digest")
    TRANSACTION_STAGED_DIGESTS+=("$staged_digest")
    if [[ -e "$final_component" || -L "$final_component" ]]; then
      move_transaction_path "$final_component" "$backup_component"
    fi
    move_transaction_path "$staged_component" "$final_component"
  done

  TRANSACTION_ACTIVE=0
  cleanup_stage
  INSTALL_STAGE=""
  release_destination_lock
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
    info "[PREVIEW] Would materialize ${display_name} → ${ws}"
    return
  fi

  info "Materializing ${display_name}..."

  # Create workspace
  mkdir -p "${ws}/skills" "${ws}/memory"

  # Copy persona files
  for f in SOUL.md AGENTS.md IDENTITY.md USER.md; do
    [[ -f "${src}/${f}" ]] && copy_file_no_clobber "${src}/${f}" "${ws}"
  done
  write_manifest_tools_no_clobber "$ws" "$agent_key"
  copy_file_no_clobber "${repo_dir}/agents/BOOTSTRAP.md" "${ws}"
  copy_file_no_clobber "${repo_dir}/agents/WORKFLOW.md" "${ws}"

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

  ok "Materialized ${display_name} → ${OPENCLAW_DIR}/workspace-${agent_key}"
}

# ── Starter Kits ──────────────────────────────────────────────
deploy_starter_kit() {
  local repo_dir="$1"
  local kit="$2"
  local filter="${3:-}"   # optional: deploy only one agent from kit

  local -a agents=()
  local kit_agent_query="kit-agents"

  if [[ -n "$MANIFEST_PATH" ]]; then
    if [[ "$(manifest_query kit-exists "$kit")" == "yes" ]]; then
      [[ "$TEAM_TIER" == "core" ]] && kit_agent_query="kit-core-agents"
      while IFS= read -r a; do
        [[ -n "$a" ]] && agents+=("$a")
      done < <(manifest_query "$kit_agent_query" "$kit")
    elif [[ "$(manifest_query agent-exists "$kit")" == "yes" ]]; then
      agents=("$kit")
    else
      err "Agent source not found: ${repo_dir}/agents/${kit}"
    fi
  else
    err "Canonical team manifest is not loaded"
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

  info "Materializing selection: ${kit} (${#agents[@]} agent(s))"

  preflight_kit_entrypoint "$repo_dir" "$kit"
  preflight_agents "$repo_dir" "${agents[@]}"
  report_recommended_external_skills "${agents[@]}"
  if [[ "$APPLY" -eq 1 ]]; then
    acquire_destination_lock
    validate_install_paths "$repo_dir" "${agents[@]}"
    prepare_stage "${agents[@]}"
  else
    validate_install_paths "$repo_dir" "${agents[@]}"
    DEPLOY_ROOT="$OPENCLAW_DIR"
  fi

  for a in "${agents[@]}"; do
    deploy_agent "$repo_dir" "$a"
  done

  if [[ "$APPLY" -eq 1 && "$LAYOUT" == "coordinated" ]]; then
    write_coordinated_team "$repo_dir" "$kit" "${agents[@]}"
  elif [[ "$LAYOUT" == "coordinated" ]]; then
    info "[PREVIEW] Would materialize managed root AGENTS.md, START_HERE.md, TEAM.md, RUNBOOK.md, and team.lock.json (not runtime verified)"
  fi

  if [[ "$APPLY" -eq 1 ]]; then
    publish_stage "${agents[@]}"
  fi

  echo ""
  ok "════════════════════════════════════════"
  if [[ "$APPLY" -eq 1 ]]; then
    ok " Kit '${kit}' materialized: ${#agents[@]} role workspace(s); runtime validation pending"
  else
    ok " PREVIEW complete for '${kit}': ${#agents[@]} agent(s)"
    info "Re-run with --apply to perform these writes."
  fi
  ok "════════════════════════════════════════"
  echo ""
  echo "Next steps:"
  if [[ "$LAYOUT" == "coordinated" ]]; then
    echo "  Open the destination root in your configured harness: ${OPENCLAW_DIR}/"
    echo "  Read AGENTS.md and START_HERE.md before submitting the team brief."
  else
    echo "  Configure your chosen harness, then open ${OPENCLAW_DIR}/workspace-<agent>/."
  fi
  echo "  Materialized files are not runtime-verified and do not prove that subagents started."
  echo "  Inspect the installed role and skills before granting tools or credentials."
  echo ""
  if [[ "$APPLY" -eq 1 ]]; then
    echo "Materialized role workspaces:"
  else
    echo "Planned agents:"
  fi
  for a in "${agents[@]}"; do
    echo "  • $(agent_name "$a") → ${OPENCLAW_DIR}/workspace-${a}/"
  done
}

# ── Main ──────────────────────────────────────────────────────
usage() {
  cat <<'EOF'
AGI Super Team generic workspace materializer

Usage:
  ./install.sh [options] (--kit ID | --agent ID)
  ./install.sh [options] <kit-or-agent> [agent-filter]

Preview is the default and requires --source so it can validate the canonical
manifest without cloning. Add --apply only after reviewing the plan.

Options:
  --source PATH                 Reviewed repository checkout
  --destination PATH            Destination root
  --kit ID                      Select a manifest starter kit
  --agent ID                    Select one Agent role pack
  --skill-tier TIER             role-only | core | standard (default)
  --team-tier TIER              core | full (default; kits only)
  --layout LAYOUT               isolated (default) | coordinated
  --apply                       Materialize the previewed payload
  -h, --help                    Show this help

Coordinated layout materializes a root team entrypoint. It does not prove that
a harness loaded roles or started subagents.
EOF
}

main() {
  local selector=""
  local -a positionals=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help) usage; return 0 ;;
      --source) [[ $# -ge 2 ]] || err "--source requires a path"; SOURCE_DIR="$2"; shift 2 ;;
      --destination) [[ $# -ge 2 ]] || err "--destination requires a path"; OPENCLAW_DIR="$2"; shift 2 ;;
      --skill-tier)
        [[ $# -ge 2 ]] || err "--skill-tier requires role-only, core, or standard"
        SKILL_TIER="$2"
        case "$SKILL_TIER" in role-only|core|standard) ;; *) err "Invalid skill tier: $SKILL_TIER" ;; esac
        shift 2
        ;;
      --team-tier)
        [[ $# -ge 2 ]] || err "--team-tier requires core or full"
        TEAM_TIER="$2"
        case "$TEAM_TIER" in core|full) ;; *) err "Invalid team tier: $TEAM_TIER" ;; esac
        shift 2
        ;;
      --layout)
        [[ $# -ge 2 ]] || err "--layout requires isolated or coordinated"
        LAYOUT="$2"
        case "$LAYOUT" in isolated|coordinated) ;; *) err "Invalid layout: $LAYOUT" ;; esac
        shift 2
        ;;
      --kit)
        [[ $# -ge 2 ]] || err "--kit requires an ID"
        [[ -z "$selector" ]] || err "Choose exactly one kit or agent"
        selector="$2"
        SELECTOR_KIND="kit"
        shift 2
        ;;
      --agent)
        [[ $# -ge 2 ]] || err "--agent requires an ID"
        [[ -z "$selector" ]] || err "Choose exactly one kit or agent"
        selector="$2"
        SELECTOR_KIND="agent"
        shift 2
        ;;
      --apply) APPLY=1; shift ;;
      --)
        shift
        while [[ $# -gt 0 ]]; do
          positionals+=("$1")
          shift
        done
        ;;
      -*) err "Unknown option: $1" ;;
      *) positionals+=("$1"); shift ;;
    esac
  done

  if [[ -n "$selector" && "${#positionals[@]}" -gt 0 ]]; then
    err "Choose one --kit/--agent selector or one legacy positional selector, not both"
  fi
  if [[ "${#positionals[@]}" -gt 2 ]]; then
    err "Unexpected extra arguments: ${positionals[*]:2}"
  fi
  if [[ -z "$SOURCE_DIR" && "$APPLY" -eq 0 ]]; then
    err "Preview for pinned ref ${REPO_REF} requires --source PATH so the canonical team manifest can be validated without cloning or inventing a plan."
  fi

  echo ""
  echo "╔══════════════════════════════════════╗"
  echo "║    🏛️  AGI Super Team Materializer   ║"
  echo "║     Preview-first role workspaces     ║"
  echo "╚══════════════════════════════════════╝"
  echo ""

  check_prereqs

  local kit="${selector:-${positionals[0]:-solo-founder}}"
  local agent_filter="${positionals[1]:-}"

  if [[ "$LAYOUT" == "coordinated" && "$SELECTOR_KIND" == "agent" ]]; then
    err "Coordinated layout requires a kit selector"
  fi
  if [[ "$LAYOUT" == "coordinated" && -n "$agent_filter" ]]; then
    err "Coordinated layout does not support a single-Agent kit filter"
  fi

  local repo_dir
  ensure_repo
  repo_dir="$RETVAL_REPO"
  load_team_manifest "$repo_dir"

  if [[ "$SELECTOR_KIND" == "kit" && "$(manifest_query kit-exists "$kit")" != "yes" ]]; then
    err "Unknown kit: $kit"
  fi
  if [[ "$SELECTOR_KIND" == "agent" && "$(manifest_query agent-exists "$kit")" != "yes" ]]; then
    err "Unknown agent: $kit"
  fi
  if [[ "$LAYOUT" == "coordinated" && "$(manifest_query kit-exists "$kit")" != "yes" ]]; then
    err "Coordinated layout requires a kit selector"
  fi

  deploy_starter_kit "$repo_dir" "$kit" "$agent_filter"
}

main "$@"
