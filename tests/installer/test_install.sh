#!/usr/bin/env bash
set -u

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
INSTALLER="${REPO_ROOT}/install.sh"
TEST_TMP=$(mktemp -d "${TMPDIR:-/tmp}/agi-installer.XXXXXX")
trap 'rm -rf "$TEST_TMP"' EXIT

failures=0

assert_file() {
  if [[ ! -f "$1" ]]; then
    printf 'not ok - expected file: %s\n' "$1"
    failures=$((failures + 1))
  fi
}

write_shared_workspace_files() {
  local source="$1"
  mkdir -p "${source}/agents"
  printf '# Charter\n' > "${source}/CHARTER.md"
  printf '# Collaboration\n' > "${source}/COLLABORATION.md"
  printf '# Bootstrap\n' > "${source}/agents/BOOTSTRAP.md"
  printf '# Workflow\n' > "${source}/agents/WORKFLOW.md"
}

write_ceo_manifest() {
  local source="$1"
  local required="${2:-team-coordinator context-manager healthcheck web-search project-planner}"
  mkdir -p "${source}/config" "${source}/starter-kits/fixture-team"
  printf '# Fixture team runbook\n' > "${source}/starter-kits/fixture-team/RUNBOOK.md"
  node - "${source}/config/team-manifest.json" "$required" <<'NODE'
const fs = require('fs');
const [path, required] = process.argv.slice(2);
const skills = required.split(/\s+/).filter(Boolean);
fs.writeFileSync(path, JSON.stringify({
  $schema: './team-manifest.schema.json', schemaVersion: 1,
  inventory: {agentCount: 3, physicalSkillCount: 0, skillEntrypoint: 'SKILL.md', symlinkPolicy: 'forbid'},
  agents: [{
    id: 'ceo', name: 'CEO', path: 'agents/ceo',
    focus: 'Set direction and make evidence-backed cross-functional decisions.',
    outputs: ['Decision memo', 'Prioritized plan'],
    boundary: 'Specialist decisions remain with their accountable domain owners.',
    skills: {
    required: skills, optional: [], harnessSpecific: [], recommendedExternal: []}}, {
    id: 'governor', name: 'Governor', path: 'agents/governor',
    focus: 'Independently review evidence and block unsupported completion claims.',
    outputs: ['Independent review', 'Gate decision'],
    boundary: 'Reviews delivery evidence without taking over implementation ownership.',
    skills: {required: [], optional: [], harnessSpecific: [], recommendedExternal: []}}, {
    id: 'pe', name: 'PE', path: 'agents/pe',
    focus: 'Implement the bounded fixture plan and return deterministic evidence.',
    outputs: ['Fixture artifact', 'Verification result'],
    boundary: 'Implements the assigned fixture without changing coordinator decisions.',
    skills: {required: [], optional: [], harnessSpecific: [], recommendedExternal: []}}],
  kits: [{
    id: 'fixture-team', name: 'Fixture Team',
    outcome: 'Exercise the installer with a bounded coordinator and reviewer fixture.',
    entrypoint: 'starter-kits/fixture-team/RUNBOOK.md', coordinator: 'ceo',
    reviewers: ['governor'], coreAgents: ['ceo', 'pe', 'governor'], agents: ['ceo', 'pe', 'governor'],
    outputs: ['Decision memo', 'Gate decision'], checks: ['plan-created', 'gate-recorded']
  }]
}));
NODE
}

write_full_team_manifest() {
  local source="$1"
  mkdir -p "${source}/config" "${source}/starter-kits/full-team"
  printf '# Full-team fixture runbook\n' > "${source}/starter-kits/full-team/RUNBOOK.md"
  node - "${source}/config/team-manifest.json" <<'NODE'
const fs = require('fs');
const path = process.argv[2];
const assignments = {
  ceo: 'team-coordinator context-manager healthcheck web-search project-planner',
  pe: 'react-expert tdd-workflow systematic-debugging code-review-quality github gh-issues deployment-automation kubernetes-specialist ghost-scan-code cli-developer',
  cco: 'xhs-publisher douyin-publisher', cto: 'api-design api-design-patterns architecture-decision architecture-patterns nginx-configuration',
  cdo: 'apify-ultimate-scraper web-search', cmo: 'seo-audit', cfo: '', cqo: '',
  cro: 'deep-research web-search', cpo: 'prd-development user-story', clo: 'legal-review',
  cso: 'crm-automation', coo: 'cost-optimization', governor: ''
};
const ids = Object.keys(assignments);
fs.writeFileSync(path, JSON.stringify({
  $schema: './team-manifest.schema.json', schemaVersion: 1,
  inventory: {agentCount: ids.length, physicalSkillCount: 0, skillEntrypoint: 'SKILL.md', symlinkPolicy: 'forbid'},
  agents: ids.map(id => ({
    id, name: id.toUpperCase(), path: `agents/${id}`,
    focus: `Own the professional ${id.toUpperCase()} operating domain and its evidence.`,
    outputs: ['Reviewed artifact', 'Verified handoff'],
    boundary: 'Escalate cross-functional decisions to the accountable domain owner.',
    skills: {
    required: assignments[id].split(/\s+/).filter(Boolean), optional: [], harnessSpecific: [], recommendedExternal: []}})),
  kits: [{
    id: 'full-team', name: 'Executive Team',
    outcome: 'Route a bounded company brief through one coordinator and independent reviewer.',
    entrypoint: 'starter-kits/full-team/RUNBOOK.md', coordinator: 'ceo',
    reviewers: ['governor'], coreAgents: ['ceo', 'coo', 'governor'], agents: ids,
    outputs: ['Routing plan', 'Reviewed handoff'], checks: ['owners-assigned', 'gate-recorded']
  }]
}));
NODE
}

test_ceo_uses_canonical_source_and_workspace() {
  local destination="${TEST_TMP}/ceo-destination"
  local output expected_skills actual_skills

  if ! output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" --apply ceo 2>&1); then
    printf 'not ok - CEO install failed\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  assert_file "${destination}/workspace-ceo/SOUL.md"
  assert_file "${destination}/workspace-ceo/skills/first-principles-thinking/SKILL.md"
  expected_skills=$(node - "${REPO_ROOT}/config/team-manifest.json" <<'NODE'
const manifest = require(process.argv[2]);
const agent = manifest.agents.find(item => item.id === 'ceo');
console.log([...agent.skills.required, ...agent.skills.optional].sort().join('\n'));
NODE
)
  actual_skills=$(find "${destination}/workspace-ceo/skills" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)
  if ! cmp -s "${REPO_ROOT}/agents/ceo/SOUL.md" "${destination}/workspace-ceo/SOUL.md"; then
    printf 'not ok - CEO persona did not come from agents/ceo\n'
    failures=$((failures + 1))
  elif [[ "$actual_skills" != "$expected_skills" ]]; then
    printf 'not ok - installed skill set differs from manifest portable assignments\nexpected:\n%s\nactual:\n%s\n' "$expected_skills" "$actual_skills"
    failures=$((failures + 1))
  elif [[ -e "${destination}/workspace-ceo/skills/team-coordinator" \
       || -e "${destination}/workspace-ceo/skills/deep-research" \
       || -e "${destination}/workspace-ceo/skills/dispatching-parallel-agents" ]]; then
    printf 'not ok - generic installer copied a harness-specific CEO skill\n'
    failures=$((failures + 1))
  elif [[ "$output" != *"Using team manifest:"* ]]; then
    printf 'not ok - installer ignored the available team manifest\n'
    failures=$((failures + 1))
  else
    printf 'ok - CEO install consumes the team manifest and canonical source\n'
  fi
}

test_ceo_uses_canonical_source_and_workspace

test_core_skill_tier_copies_only_required_skills() {
  local destination="${TEST_TMP}/core-skill-tier-destination"
  local output expected_skills actual_skills optional_skill

  if ! output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" \
    --skill-tier core --apply --agent ceo 2>&1); then
    printf 'not ok - core skill tier install failed\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  expected_skills=$(node - "${REPO_ROOT}/config/team-manifest.json" <<'NODE'
const manifest = require(process.argv[2]);
const agent = manifest.agents.find(item => item.id === 'ceo');
console.log(agent.skills.required.slice().sort().join('\n'));
NODE
  )
  actual_skills=$(find "${destination}/workspace-ceo/skills" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)
  optional_skill=$(node - "${REPO_ROOT}/config/team-manifest.json" <<'NODE'
const manifest = require(process.argv[2]);
const agent = manifest.agents.find(item => item.id === 'ceo');
console.log(agent.skills.optional[0] || '');
NODE
  )

  if [[ "$actual_skills" == "$expected_skills" \
     && ( -z "$optional_skill" || ! -e "${destination}/workspace-ceo/skills/${optional_skill}" ) ]]; then
    printf 'ok - core skill tier copies required skills only\n'
  else
    printf 'not ok - core skill tier copied the wrong Skill set\nexpected:\n%s\nactual:\n%s\n' \
      "$expected_skills" "$actual_skills"
    failures=$((failures + 1))
  fi
}

test_core_skill_tier_copies_only_required_skills

test_role_only_skill_tier_materializes_no_skills() {
  local destination="${TEST_TMP}/role-only-tier-destination"
  local output

  if ! output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" \
    --skill-tier role-only --apply --agent cpo 2>&1); then
    printf 'not ok - role-only skill tier install failed\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  if [[ -d "${destination}/workspace-cpo/skills" \
     && -z "$(find "${destination}/workspace-cpo/skills" -mindepth 1 -print -quit)" ]] \
     && ! grep -q '](skills/' "${destination}/workspace-cpo/TOOLS.md"; then
    printf 'ok - role-only skill tier materializes role files without Skills\n'
  else
    printf 'not ok - role-only skill tier materialized a Skill assignment\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_role_only_skill_tier_materializes_no_skills

test_full_team_installs_all_agent_directories() {
  local destination="${TEST_TMP}/full-team-destination"
  local output agent count=0

  if ! output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" --apply full-team 2>&1); then
    printf 'not ok - full-team install failed\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  for agent in cco cdo ceo cfo clo cmo coo cpo cqo cro cso cto governor pe; do
    if [[ -f "${destination}/workspace-${agent}/SOUL.md" ]]; then
      count=$((count + 1))
    else
      printf 'not ok - full-team omitted %s\n' "$agent"
      failures=$((failures + 1))
    fi
  done

  if [[ "$count" -eq 14 ]]; then
    printf 'ok - full-team installs all 14 agent directories\n'
  fi

  if [[ -f "${destination}/agents/CHARTER.md" \
     && -f "${destination}/agents/COLLABORATION.md" \
     && -f "${destination}/workspace-ceo/WORKFLOW.md" ]] \
     && ! grep -E -q '~/.openclaw/agents|~/clawd|/Users/|/home/' \
       "${destination}"/workspace-*/*.md "${destination}/agents"/*.md; then
    printf 'ok - installed shared docs and role references are portable\n'
  else
    printf 'not ok - installed role content has missing or host-specific shared docs\n'
    failures=$((failures + 1))
  fi

  if [[ "$output" == *"recommended external skill(s) are not bundled"* \
     && "$output" != *"Optional skill unavailable:"* ]]; then
    printf 'ok - full-team reports recommended external skills without treating them as install warnings\n'
  else
    printf 'not ok - full-team emitted normal warnings for recommended external skills\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_full_team_installs_all_agent_directories

test_coordinated_layout_materializes_a_ceo_led_team_entrypoint() {
  local destination="${TEST_TMP}/coordinated-full-team-destination"
  local output status=0

  if ! output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" \
    --layout coordinated --team-tier full --skill-tier role-only --apply --kit full-team 2>&1); then
    printf 'not ok - coordinated full-team install failed\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  for file in AGENTS.md START_HERE.md TEAM.md RUNBOOK.md team.lock.json; do
    assert_file "${destination}/${file}"
  done

  node - "$destination" <<'NODE' || status=$?
const crypto = require('crypto');
const fs = require('fs');
const root = process.argv[2];
const lock = JSON.parse(fs.readFileSync(`${root}/team.lock.json`, 'utf8'));
const manifestPath = `${process.cwd()}/config/team-manifest.json`;
const manifestBytes = fs.readFileSync(manifestPath);
const manifest = JSON.parse(manifestBytes);
const kit = manifest.kits.find(item => item.id === 'full-team');
const expectedDigest = crypto.createHash('sha256').update(manifestBytes).digest('hex');
if (lock.status !== 'materialized' || lock.runtimeVerified !== false
    || lock.managedBy !== 'agi-super-team-installer'
    || lock.layout !== 'coordinated' || lock.skillTier !== 'role-only'
    || lock.teamTier !== 'full' || lock.selector !== 'full-team'
    || lock.coordinator !== 'ceo' || !lock.reviewers.includes('governor')
    || lock.agents.length !== 14 || lock.entrypoint !== kit.entrypoint
    || lock.manifestDigest !== expectedDigest
    || JSON.stringify(lock.outputs) !== JSON.stringify(kit.outputs)
    || JSON.stringify(lock.checks) !== JSON.stringify(kit.checks)) process.exit(1);
const agents = fs.readFileSync(`${root}/AGENTS.md`, 'utf8');
const start = fs.readFileSync(`${root}/START_HERE.md`, 'utf8');
const team = fs.readFileSync(`${root}/TEAM.md`, 'utf8');
const runbook = fs.readFileSync(`${root}/RUNBOOK.md`, 'utf8');
for (const text of [agents, start, team, runbook]) {
  if (!text.startsWith('<!-- managed-by: agi-super-team-installer -->')) process.exit(2);
}
if (!/read `RUNBOOK\.md` first/i.test(agents) || !/read `RUNBOOK\.md` first/i.test(start)
    || !/CEO coordinator/i.test(agents) || !/workspace-ceo/.test(agents)
    || !/delegation capability/i.test(agents)
    || !/sequential\/manual/i.test(agents)
    || /subagents? (?:have been|were) started/i.test(agents)
    || !/open this destination root/i.test(start)
    || !/Coordinator.*workspace-ceo/i.test(team)
    || !/Reviewer.*workspace-governor/i.test(team)) process.exit(3);
NODE

  if [[ "$status" -eq 0 ]]; then
    printf 'ok - coordinated layout exposes a CEO-led team with an honest fallback\n'
  else
    printf 'not ok - coordinated layout entrypoint or lock contract is incomplete\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_coordinated_layout_materializes_a_ceo_led_team_entrypoint

test_coordinated_layout_rejects_unmanaged_root_contracts() {
  local destination="${TEST_TMP}/unmanaged-root-destination"
  local output status=0

  mkdir -p "$destination"
  printf '# My project instructions\n' > "${destination}/AGENTS.md"

  output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" \
    --layout coordinated --team-tier core --skill-tier role-only --apply --kit full-team 2>&1) || status=$?

  if [[ "$status" -ne 0 && "$output" == *"not installer-managed"* \
     && "$(<"${destination}/AGENTS.md")" == '# My project instructions' \
     && ! -e "${destination}/team.lock.json" && ! -e "${destination}/workspace-ceo" ]]; then
    printf 'ok - coordinated install fails closed on an unmanaged root contract\n'
  else
    printf 'not ok - coordinated install overwrote or ignored an unmanaged root contract\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_coordinated_layout_rejects_unmanaged_root_contracts

test_coordinated_reinstall_refreshes_managed_contracts_and_preserves_old_workspaces() {
  local destination="${TEST_TMP}/coordinated-refresh-destination"
  local first_output second_output status=0

  if ! first_output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" \
    --layout coordinated --team-tier core --skill-tier role-only --apply --kit full-team 2>&1); then
    printf 'not ok - initial coordinated install for refresh test failed\n%s\n' "$first_output"
    failures=$((failures + 1))
    return
  fi
  if ! second_output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" \
    --layout coordinated --team-tier full --skill-tier role-only --apply --kit solo-founder 2>&1); then
    printf 'not ok - coordinated managed refresh failed\n%s\n' "$second_output"
    failures=$((failures + 1))
    return
  fi

  node - "$destination" "$REPO_ROOT" <<'NODE' || status=$?
const fs = require('fs');
const [root, repo] = process.argv.slice(2);
const manifest = JSON.parse(fs.readFileSync(`${repo}/config/team-manifest.json`, 'utf8'));
const kit = manifest.kits.find(item => item.id === 'solo-founder');
const lock = JSON.parse(fs.readFileSync(`${root}/team.lock.json`, 'utf8'));
const team = fs.readFileSync(`${root}/TEAM.md`, 'utf8');
const runbook = fs.readFileSync(`${root}/RUNBOOK.md`, 'utf8');
if (lock.selector !== 'solo-founder' || lock.teamTier !== 'full'
    || JSON.stringify(lock.agents) !== JSON.stringify(kit.agents)
    || lock.agents.includes('coo') || /workspace-coo/.test(team)
    || !/Unlisted workspace directories/.test(team)
    || !runbook.includes(fs.readFileSync(`${repo}/${kit.entrypoint}`, 'utf8').trim())) process.exit(1);
NODE

  if [[ "$status" -eq 0 && -d "${destination}/workspace-coo" ]]; then
    printf 'ok - coordinated reinstall refreshes managed facts and preserves unlisted old workspaces\n'
  else
    printf 'not ok - coordinated reinstall left stale facts or deleted an old workspace\n%s\n' "$second_output"
    failures=$((failures + 1))
  fi
}

test_coordinated_reinstall_refreshes_managed_contracts_and_preserves_old_workspaces

test_core_team_tier_uses_manifest_core_agents() {
  local destination="${TEST_TMP}/core-team-tier-destination"
  local output expected actual

  if ! output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" \
    --team-tier core --skill-tier role-only --apply --kit solo-founder 2>&1); then
    printf 'not ok - core team tier install failed\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  expected=$(node - "${REPO_ROOT}/config/team-manifest.json" <<'NODE'
const manifest = require(process.argv[2]);
console.log(manifest.kits.find(kit => kit.id === 'solo-founder').coreAgents.slice().sort().join('\n'));
NODE
  )
  actual=$(find "$destination" -mindepth 1 -maxdepth 1 -type d -name 'workspace-*' \
    -exec basename {} \; | sed 's/^workspace-//' | sort)

  if [[ "$actual" == "$expected" ]]; then
    printf 'ok - core team tier materializes exactly the manifest coreAgents\n'
  else
    printf 'not ok - core team tier differs from manifest coreAgents\nexpected:\n%s\nactual:\n%s\n' \
      "$expected" "$actual"
    failures=$((failures + 1))
  fi
}

test_core_team_tier_uses_manifest_core_agents

test_recommended_external_skills_are_informational() {
  local destination="${TEST_TMP}/optional-skill-destination"
  local output

  if ! output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" --apply ceo 2>&1); then
    printf 'not ok - CEO install failed while checking optional skills\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  if [[ "$output" == *"recommended external skill(s) are not bundled"* \
     && "$output" != *"Optional skill unavailable:"* ]]; then
    printf 'ok - recommended external skills are informational\n'
  else
    printf 'not ok - recommended external skill classification was wrong\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_recommended_external_skills_are_informational

test_installed_tools_links_are_workspace_local_and_resolve() {
  local destination="${TEST_TMP}/tools-link-destination"
  local workspace="${destination}/workspace-coo"
  local output linked_skill

  if ! output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" --apply coo 2>&1); then
    printf 'not ok - COO install failed while checking TOOLS links\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  if grep -q '../../skills/' "${workspace}/TOOLS.md"; then
    printf 'not ok - installed TOOLS.md retained repository-relative links\n'
    failures=$((failures + 1))
    return
  fi

  while IFS= read -r linked_skill; do
    if [[ ! -f "${workspace}/skills/${linked_skill}/SKILL.md" ]]; then
      printf 'not ok - installed TOOLS.md link does not resolve: %s\n' "$linked_skill"
      failures=$((failures + 1))
      return
    fi
  done < <(sed -nE 's#.*\]\(skills/([^/)]+)/?\).*#\1#p' "${workspace}/TOOLS.md")

  printf 'ok - installed TOOLS.md links are workspace-local and resolve\n'
}

test_installed_tools_links_are_workspace_local_and_resolve

test_preview_is_default_and_does_not_write() {
  local destination="${TEST_TMP}/preview-destination"
  local output

  if ! output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" ceo 2>&1); then
    printf 'not ok - default preview failed\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  if [[ -e "$destination" ]]; then
    printf 'not ok - preview wrote to destination\n'
    failures=$((failures + 1))
  elif [[ "$output" == *"PREVIEW"* && "$output" == *"workspace-ceo"* && "$output" == *"Re-run with --apply"* ]]; then
    printf 'ok - preview is default and does not write\n'
  else
    printf 'not ok - preview did not describe the planned write\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_preview_is_default_and_does_not_write

test_options_are_accepted_after_a_legacy_positional_selector() {
  local destination="${TEST_TMP}/options-anywhere-destination"
  local output

  if ! output=$(bash "$INSTALLER" ceo --skill-tier role-only --destination "$destination" \
    --source "$REPO_ROOT" --apply 2>&1); then
    printf 'not ok - options after positional selector failed\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  if [[ -f "${destination}/workspace-ceo/SOUL.md" \
     && -z "$(find "${destination}/workspace-ceo/skills" -mindepth 1 -print -quit)" ]]; then
    printf 'ok - options are accepted after a legacy positional selector\n'
  else
    printf 'not ok - options after positional selector selected the wrong payload\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_options_are_accepted_after_a_legacy_positional_selector

test_help_and_argument_errors_are_explicit() {
  local help_output extra_output help_status=0 extra_status=0

  help_output=$(bash "$INSTALLER" --help 2>&1) || help_status=$?
  extra_output=$(bash "$INSTALLER" --source "$REPO_ROOT" ceo extra unexpected 2>&1) || extra_status=$?

  if [[ "$help_status" -eq 0 && "$help_output" == *"--skill-tier"* \
     && "$help_output" == *"--layout"* && "$help_output" == *"--kit"* \
     && "$extra_status" -ne 0 && "$extra_output" == *"Unexpected extra arguments"* ]]; then
    printf 'ok - help documents the layered Interface and extra arguments fail explicitly\n'
  else
    printf 'not ok - help or extra-argument handling is incomplete\nhelp:\n%s\nextra:\n%s\n' \
      "$help_output" "$extra_output"
    failures=$((failures + 1))
  fi
}

test_help_and_argument_errors_are_explicit

test_explicit_selector_kind_is_enforced() {
  local kit_output agent_output kit_status=0 agent_status=0

  kit_output=$(bash "$INSTALLER" --source "$REPO_ROOT" --kit ceo 2>&1) || kit_status=$?
  agent_output=$(bash "$INSTALLER" --source "$REPO_ROOT" --agent solo-founder 2>&1) || agent_status=$?

  if [[ "$kit_status" -ne 0 && "$kit_output" == *"Unknown kit"* \
     && "$agent_status" -ne 0 && "$agent_output" == *"Unknown agent"* ]]; then
    printf 'ok - explicit kit and agent selectors reject the wrong manifest kind\n'
  else
    printf 'not ok - explicit selector kind was silently reinterpreted\nkit:\n%s\nagent:\n%s\n' \
      "$kit_output" "$agent_output"
    failures=$((failures + 1))
  fi
}

test_explicit_selector_kind_is_enforced

test_apply_preserves_existing_persona_and_user_files() {
  local destination="${TEST_TMP}/no-clobber-destination"
  local workspace="${destination}/workspace-ceo"
  local output

  mkdir -p "$workspace"
  printf '%s\n' 'my existing persona' > "${workspace}/SOUL.md"
  printf '%s\n' 'my existing user preferences' > "${workspace}/USER.md"

  if ! output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" --apply ceo 2>&1); then
    printf 'not ok - no-clobber install failed\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  if [[ "$(<"${workspace}/SOUL.md")" != 'my existing persona' \
     || "$(<"${workspace}/USER.md")" != 'my existing user preferences' ]]; then
    printf 'not ok - apply overwrote existing persona or user content\n'
    failures=$((failures + 1))
  elif [[ "$output" == *"Preserved existing file"* ]]; then
    printf 'ok - apply preserves and reports existing persona/user content\n'
  else
    printf 'not ok - preserved files were not reported\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_apply_preserves_existing_persona_and_user_files

test_unknown_agent_fails_instead_of_claiming_success() {
  local destination="${TEST_TMP}/unknown-agent-destination"
  local output status=0

  output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" --apply not-a-real-agent 2>&1) || status=$?
  if [[ "$status" -ne 0 && "$output" == *"Agent source not found"* && "$output" != *"deployed!"* ]]; then
    printf 'ok - unknown agents fail explicitly\n'
  else
    printf 'not ok - unknown agent was reported as deployed\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_unknown_agent_fails_instead_of_claiming_success

test_missing_shared_doc_fails_preflight_without_writes() {
  local source="${TEST_TMP}/missing-shared-doc-source"
  local destination="${TEST_TMP}/missing-shared-doc-destination"
  local output status=0 skill

  mkdir -p "${source}/agents/ceo" "${source}/skills"
  write_ceo_manifest "$source"
  printf '# CEO\n' > "${source}/agents/ceo/AGENTS.md"
  printf '# Collaboration\n' > "${source}/COLLABORATION.md"
  for skill in team-coordinator context-manager healthcheck web-search project-planner; do
    mkdir -p "${source}/skills/${skill}"
    printf '# %s\n' "$skill" > "${source}/skills/${skill}/SKILL.md"
  done

  output=$(bash "$INSTALLER" --source "$source" --destination "$destination" --apply ceo 2>&1) || status=$?
  if [[ "$status" -ne 0 && "$output" == *"Required shared workspace file unavailable: CHARTER.md"* \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - missing shared workspace docs fail preflight with zero writes\n'
  else
    printf 'not ok - missing shared workspace doc was not fail-closed\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_missing_shared_doc_fails_preflight_without_writes

test_manifest_path_traversal_is_rejected_before_writes() {
  local source="${TEST_TMP}/traversal-source"
  local outside="${TEST_TMP}/outside-agent"
  local destination="${TEST_TMP}/traversal-destination"
  local output status=0

  mkdir -p "${source}/config" "${source}/skills" "$outside"
  write_shared_workspace_files "$source"
  printf '# Outside\n' > "${outside}/SOUL.md"
  printf '%s\n' '{"$schema":"./team-manifest.schema.json","schemaVersion":1,"inventory":{"agentCount":1,"physicalSkillCount":0,"skillEntrypoint":"SKILL.md","symlinkPolicy":"forbid"},"agents":[{"id":"ceo","name":"CEO","path":"../outside-agent","skills":{"required":[],"optional":[],"harnessSpecific":[],"recommendedExternal":[]}}],"kits":[{"id":"ceo","agents":["ceo"]}]}' \
    > "${source}/config/team-manifest.json"

  output=$(bash "$INSTALLER" --source "$source" --destination "$destination" --apply ceo 2>&1) || status=$?
  if [[ "$status" -ne 0 && "$output" == *"Invalid team manifest"* \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - manifest path traversal is rejected before writes\n'
  else
    printf 'not ok - manifest path traversal escaped the source boundary\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_manifest_path_traversal_is_rejected_before_writes

test_manifest_schema_required_fields_are_enforced() {
  local source="${TEST_TMP}/schema-source"
  local destination="${TEST_TMP}/schema-destination"
  local output status=0

  write_shared_workspace_files "$source"
  mkdir -p "${source}/agents/ceo" "${source}/skills"
  write_ceo_manifest "$source"
  node - "${source}/config/team-manifest.json" <<'NODE'
const fs = require('fs');
const path = process.argv[2];
const manifest = JSON.parse(fs.readFileSync(path, 'utf8'));
delete manifest.inventory;
fs.writeFileSync(path, JSON.stringify(manifest));
NODE

  output=$(bash "$INSTALLER" --source "$source" --destination "$destination" --apply ceo 2>&1) || status=$?
  if [[ "$status" -ne 0 && "$output" == *"Invalid team manifest"* \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - installer enforces manifest Schema-required inventory before writes\n'
  else
    printf 'not ok - installer accepted a manifest missing a Schema-required field\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_manifest_schema_required_fields_are_enforced

test_manifest_schema_min_items_are_enforced() {
  local source="${TEST_TMP}/schema-min-items-source"
  local destination="${TEST_TMP}/schema-min-items-destination"
  local output status=0

  write_shared_workspace_files "$source"
  mkdir -p "${source}/agents/ceo" "${source}/skills"
  write_ceo_manifest "$source"
  node - "${source}/config/team-manifest.json" <<'NODE'
const fs = require('fs');
const path = process.argv[2];
const manifest = JSON.parse(fs.readFileSync(path, 'utf8'));
manifest.kits[0].agents = [];
fs.writeFileSync(path, JSON.stringify(manifest));
NODE

  output=$(bash "$INSTALLER" --source "$source" --destination "$destination" --apply ceo 2>&1) || status=$?
  if [[ "$status" -ne 0 && "$output" == *"Invalid team manifest"* \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - installer enforces manifest Schema minItems before writes\n'
  else
    printf 'not ok - installer accepted a Schema-invalid empty kit assignment\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_manifest_schema_min_items_are_enforced

test_legacy_kit_shape_is_rejected() {
  local source="${TEST_TMP}/legacy-kit-source"
  local destination="${TEST_TMP}/legacy-kit-destination"
  local output status=0

  write_shared_workspace_files "$source"
  mkdir -p "${source}/agents/ceo" "${source}/skills"
  write_ceo_manifest "$source"
  node - "${source}/config/team-manifest.json" <<'NODE'
const fs = require('fs');
const path = process.argv[2];
const manifest = JSON.parse(fs.readFileSync(path, 'utf8'));
manifest.kits[0] = {id: 'fixture-team', agents: ['ceo', 'pe', 'governor']};
fs.writeFileSync(path, JSON.stringify(manifest));
NODE

  output=$(bash "$INSTALLER" --source "$source" --destination "$destination" --apply --agent ceo 2>&1) || status=$?
  if [[ "$status" -ne 0 && "$output" == *"Invalid team manifest"* \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - legacy kit shapes are rejected before writes\n'
  else
    printf 'not ok - installer accepted a legacy kit shape\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_legacy_kit_shape_is_rejected

test_coordinator_and_reviewer_must_be_distinct_core_members() {
  local source="${TEST_TMP}/invalid-kit-relationship-source"
  local destination="${TEST_TMP}/invalid-kit-relationship-destination"
  local output status=0

  write_shared_workspace_files "$source"
  mkdir -p "${source}/agents/ceo" "${source}/skills"
  write_ceo_manifest "$source"
  node - "${source}/config/team-manifest.json" <<'NODE'
const fs = require('fs');
const path = process.argv[2];
const manifest = JSON.parse(fs.readFileSync(path, 'utf8'));
manifest.kits[0].reviewers = ['ceo'];
fs.writeFileSync(path, JSON.stringify(manifest));
NODE

  output=$(bash "$INSTALLER" --source "$source" --destination "$destination" --apply --agent ceo 2>&1) || status=$?
  if [[ "$status" -ne 0 && "$output" == *"Invalid team manifest"* \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - coordinator and reviewer relationships fail closed before writes\n'
  else
    printf 'not ok - installer accepted an invalid coordinator/reviewer relationship\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_coordinator_and_reviewer_must_be_distinct_core_members

test_missing_manifest_fails_before_writes() {
  local source="${TEST_TMP}/missing-manifest-source"
  local destination="${TEST_TMP}/missing-manifest-destination"
  local output status=0

  mkdir -p "${source}/agents/ceo" "${source}/skills"
  write_shared_workspace_files "$source"
  output=$(bash "$INSTALLER" --source "$source" --destination "$destination" --apply ceo 2>&1) || status=$?
  if [[ "$status" -ne 0 && "$output" == *"Required team manifest unavailable"* \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - a local apply without the canonical manifest performs zero writes\n'
  else
    printf 'not ok - local apply used a second source of truth without the manifest\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_missing_manifest_fails_before_writes

test_full_team_preflight_fails_before_any_write() {
  local source="${TEST_TMP}/preflight-source"
  local destination="${TEST_TMP}/preflight-destination"
  local output status=0 agent skill

  write_shared_workspace_files "$source"
  write_full_team_manifest "$source"

  for agent in cco cdo ceo cfo clo cmo coo cpo cqo cro cso cto governor pe; do
    mkdir -p "${source}/agents/${agent}"
  done

  for skill in \
    team-coordinator context-manager healthcheck web-search project-planner \
    react-expert tdd-workflow systematic-debugging code-review-quality github \
    gh-issues deployment-automation kubernetes-specialist ghost-scan-code cli-developer \
    xhs-publisher douyin-publisher api-design api-design-patterns architecture-decision \
    architecture-patterns nginx-configuration apify-ultimate-scraper seo-audit \
    deep-research prd-development user-story legal-review crm-automation; do
    mkdir -p "${source}/skills/${skill}"
  done

  output=$(bash "$INSTALLER" --source "$source" --destination "$destination" --apply full-team 2>&1) || status=$?
  if [[ "$status" -ne 0 && "$output" == *"Required skill unavailable: cost-optimization"* \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - full-team preflight failure performs zero destination writes\n'
  else
    printf 'not ok - full-team failure wrote before preflight completed\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_full_team_preflight_fails_before_any_write

test_apply_rejects_a_broken_destination_symlink() {
  local destination="${TEST_TMP}/broken-destination-link"
  local target="${TEST_TMP}/missing-destination-target"
  local output status=0

  ln -s "$target" "$destination"
  output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" --apply ceo 2>&1) || status=$?

  if [[ "$status" -ne 0 && "$output" == *"Destination path must not be a symlink"* \
     && -L "$destination" && ! -e "$target" ]]; then
    printf 'ok - apply rejects a broken destination symlink\n'
  else
    printf 'not ok - apply did not safely reject a broken destination symlink\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_apply_rejects_a_broken_destination_symlink

test_failed_staging_does_not_publish_a_partial_workspace() {
  local source="${TEST_TMP}/atomic-source"
  local destination="${TEST_TMP}/atomic-destination"
  local fake_bin="${TEST_TMP}/atomic-bin"
  local output status=0 skill

  mkdir -p "${source}/agents/ceo" "${source}/skills" "$fake_bin"
  write_shared_workspace_files "$source"
  write_ceo_manifest "$source"
  printf '%s\n' 'test persona' > "${source}/agents/ceo/SOUL.md"
  for skill in team-coordinator context-manager healthcheck web-search project-planner; do
    mkdir -p "${source}/skills/${skill}"
  done
  printf '%s\n' '#!/usr/bin/env sh' 'exit 77' > "${fake_bin}/cp"
  chmod +x "${fake_bin}/cp"

  output=$(PATH="${fake_bin}:$PATH" bash "$INSTALLER" \
    --source "$source" --destination "$destination" --apply ceo 2>&1) || status=$?

  if [[ "$status" -ne 0 && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - failed staging does not publish a partial workspace\n'
  else
    printf 'not ok - failed staging left destination writes behind\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_failed_staging_does_not_publish_a_partial_workspace

test_publish_failure_restores_existing_components() {
  local destination="${TEST_TMP}/publish-rollback-destination"
  local fake_bin="${TEST_TMP}/publish-rollback-bin"
  local counter="${TEST_TMP}/publish-rollback-count"
  local output status=0

  mkdir -p "${destination}/agents" "${destination}/workspace-ceo" "$fake_bin"
  printf 'old shared state\n' > "${destination}/agents/marker.txt"
  printf 'old persona\n' > "${destination}/workspace-ceo/SOUL.md"
  printf '0\n' > "$counter"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    "counter='$counter'" \
    'count=$(($(cat "$counter") + 1))' \
    'printf "%s\n" "$count" > "$counter"' \
    'if [[ "$count" -eq 3 ]]; then exit 77; fi' \
    'exec /bin/mv "$@"' > "${fake_bin}/mv"
  chmod +x "${fake_bin}/mv"

  output=$(PATH="${fake_bin}:$PATH" bash "$INSTALLER" \
    --source "$REPO_ROOT" --destination "$destination" --apply ceo 2>&1) || status=$?

  if [[ "$status" -ne 0 && "$output" == *"restored the previous destination state"* \
     && "$(<"${destination}/agents/marker.txt")" == "old shared state" \
     && "$(<"${destination}/workspace-ceo/SOUL.md")" == "old persona" \
     && ! -e "${destination}/workspace-ceo/skills" ]]; then
    printf 'ok - a mid-publish failure restores every existing component\n'
  else
    printf 'not ok - publish rollback did not restore the previous destination\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_publish_failure_restores_existing_components

test_publish_signal_restores_existing_components() {
  local signal_name signal_status destination fake_bin counter output status lock_path

  for signal_name in HUP INT TERM; do
    case "$signal_name" in HUP) signal_status=129 ;; INT) signal_status=130 ;; TERM) signal_status=143 ;; esac
    destination="${TEST_TMP}/publish-${signal_name}-destination"
    fake_bin="${TEST_TMP}/publish-${signal_name}-bin"
    counter="${TEST_TMP}/publish-${signal_name}-count"
    lock_path="${TEST_TMP}/.publish-${signal_name}-destination.agi-super-team-install.lock"
    status=0

    mkdir -p "${destination}/agents" "${destination}/workspace-ceo" "$fake_bin"
    printf 'old shared state\n' > "${destination}/agents/marker.txt"
    printf 'old persona\n' > "${destination}/workspace-ceo/SOUL.md"
    printf '0\n' > "$counter"
    printf '%s\n' \
      '#!/usr/bin/env bash' \
      "counter='$counter'" \
      "signal_status='$signal_status'" \
      'count=$(($(cat "$counter") + 1))' \
      'printf "%s\n" "$count" > "$counter"' \
      'if [[ "$count" -eq 3 ]]; then' \
      '  /bin/mv "$@" || exit $?' \
      '  exit "$signal_status"' \
      'fi' \
      'exec /bin/mv "$@"' > "${fake_bin}/mv"
    chmod +x "${fake_bin}/mv"

    output=$(PATH="${fake_bin}:$PATH" bash "$INSTALLER" \
      --source "$REPO_ROOT" --destination "$destination" --apply ceo 2>&1) || status=$?

    if [[ "$status" -eq 0 || "$output" != *"Received ${signal_name}; restored the previous destination state"* \
       || "$(<"${destination}/agents/marker.txt")" != "old shared state" \
       || "$(<"${destination}/workspace-ceo/SOUL.md")" != "old persona" \
       || -e "${destination}/workspace-ceo/skills" || -e "$lock_path" ]]; then
      printf 'not ok - %s publish interruption did not restore state and release its lock\n%s\n' \
        "$signal_name" "$output"
      failures=$((failures + 1))
      return
    fi
  done
  printf 'ok - HUP, INT, and TERM publish interruptions restore state and release locks\n'
}

test_publish_signal_restores_existing_components

test_new_destination_interruption_quarantines_the_tagged_publish() {
  local destination="${TEST_TMP}/new-root-signal-destination"
  local fake_bin="${TEST_TMP}/new-root-signal-bin"
  local output status=0 recovery_path

  mkdir -p "$fake_bin"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    '/bin/mv "$@" || exit $?' \
    'exit 143' > "${fake_bin}/mv"
  chmod +x "${fake_bin}/mv"

  output=$(PATH="${fake_bin}:$PATH" bash "$INSTALLER" --source "$REPO_ROOT" \
    --destination "$destination" --apply ceo 2>&1) || status=$?
  recovery_path=$(printf '%s\n' "$output" | sed -n 's/.*Recovery transaction preserved at: //p' | tail -1)

  if [[ "$status" -ne 0 && "$output" == *"automatic restore is incomplete"* \
     && -n "$recovery_path" && -d "${recovery_path}/recovery-destination" \
     && -f "${recovery_path}/recovery-destination/workspace-ceo/AGENTS.md" \
     && ! -e "$destination" && ! -L "$destination" \
     && ! -e "${TEST_TMP}/.new-root-signal-destination.agi-super-team-install.lock" ]]; then
    printf 'ok - interrupted first install quarantines its tagged destination and releases its lock\n'
  else
    printf 'not ok - interrupted first install did not preserve a recovery destination\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_new_destination_interruption_quarantines_the_tagged_publish

test_new_destination_drift_during_interruption_is_quarantined() {
  local destination="${TEST_TMP}/new-root-drift-destination"
  local fake_bin="${TEST_TMP}/new-root-drift-bin"
  local counter="${TEST_TMP}/new-root-drift-count"
  local output status=0 recovery_path

  mkdir -p "$fake_bin"
  printf '0\n' > "$counter"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    "counter='$counter'" \
    'count=$(($(cat "$counter") + 1))' \
    'printf "%s\n" "$count" > "$counter"' \
    'if [[ "$count" -eq 1 ]]; then' \
    '  /bin/mv "$@" || exit $?' \
    '  printf "user concurrent data\n" > "$2/user-concurrent.txt"' \
    '  exit 143' \
    'fi' \
    'exec /bin/mv "$@"' > "${fake_bin}/mv"
  chmod +x "${fake_bin}/mv"

  output=$(PATH="${fake_bin}:$PATH" bash "$INSTALLER" --source "$REPO_ROOT" \
    --destination "$destination" --apply ceo 2>&1) || status=$?
  recovery_path=$(printf '%s\n' "$output" | sed -n 's/.*Recovery transaction preserved at: //p' | tail -1)

  if [[ "$status" -ne 0 && "$output" == *"automatic restore is incomplete"* \
     && -n "$recovery_path" && -d "$recovery_path" \
     && "$(<"${recovery_path}/recovery-destination/user-concurrent.txt")" == "user concurrent data" \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - concurrent data in an interrupted new destination is quarantined, not deleted\n'
  else
    printf 'not ok - interrupted new-destination drift was deleted or lost\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_new_destination_drift_during_interruption_is_quarantined

test_new_destination_drift_survives_failed_quarantine() {
  local destination="${TEST_TMP}/new-root-drift-stays-destination"
  local fake_bin="${TEST_TMP}/new-root-drift-stays-bin"
  local counter="${TEST_TMP}/new-root-drift-stays-count"
  local output status=0 recovery_path

  mkdir -p "$fake_bin"
  printf '0\n' > "$counter"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    "counter='$counter'" \
    'count=$(($(cat "$counter") + 1))' \
    'printf "%s\n" "$count" > "$counter"' \
    'if [[ "$count" -eq 1 ]]; then' \
    '  /bin/mv "$@" || exit $?' \
    '  printf "user concurrent data\n" > "$2/user-concurrent.txt"' \
    '  exit 143' \
    'fi' \
    'exit 77' > "${fake_bin}/mv"
  chmod +x "${fake_bin}/mv"

  output=$(PATH="${fake_bin}:$PATH" bash "$INSTALLER" --source "$REPO_ROOT" \
    --destination "$destination" --apply ceo 2>&1) || status=$?
  recovery_path=$(printf '%s\n' "$output" | sed -n 's/.*Recovery transaction preserved at: //p' | tail -1)

  if [[ "$status" -ne 0 && "$output" == *"automatic restore is incomplete"* \
     && -n "$recovery_path" && -d "$recovery_path" \
     && "$(<"${destination}/user-concurrent.txt")" == "user concurrent data" ]]; then
    printf 'ok - failed quarantine leaves concurrent data in place and reports recovery state\n'
  else
    printf 'not ok - failed quarantine deleted concurrent destination data\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_new_destination_drift_survives_failed_quarantine

test_destination_lock_blocks_a_second_installer() {
  local destination="${TEST_TMP}/lock-destination"
  local fake_bin="${TEST_TMP}/lock-bin"
  local ready="${TEST_TMP}/lock-ready"
  local release="${TEST_TMP}/lock-release"
  local first_output="${TEST_TMP}/lock-first-output"
  local second_output second_status=0 first_status=0 first_pid attempt

  mkdir -p "$destination" "$fake_bin"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    "ready='$ready'" \
    "release='$release'" \
    'if [[ ! -e "$ready" ]]; then' \
    '  : > "$ready"' \
    '  while [[ ! -e "$release" ]]; do sleep 0.02; done' \
    'fi' \
    'exec /bin/cp "$@"' > "${fake_bin}/cp"
  chmod +x "${fake_bin}/cp"

  PATH="${fake_bin}:$PATH" bash "$INSTALLER" --source "$REPO_ROOT" \
    --destination "$destination" --apply ceo > "$first_output" 2>&1 &
  first_pid=$!
  for attempt in $(seq 1 100); do
    [[ -e "$ready" ]] && break
    sleep 0.02
  done

  second_output=$(bash "$INSTALLER" --source "$REPO_ROOT" \
    --destination "$destination" --apply ceo 2>&1) || second_status=$?
  : > "$release"
  wait "$first_pid" || first_status=$?

  if [[ "$first_status" -eq 0 && "$second_status" -ne 0 \
     && "$second_output" == *"Another installation is active for destination"* \
     && ! -e "${TEST_TMP}/.lock-destination.agi-super-team-install.lock" ]]; then
    printf 'ok - destination lock blocks a second installer\n'
  else
    printf 'not ok - two installers could publish the same destination concurrently\nfirst:\n%s\nsecond:\n%s\n' \
      "$(<"$first_output")" "$second_output"
    failures=$((failures + 1))
  fi
}

test_destination_lock_blocks_a_second_installer

test_destination_drift_aborts_before_publish() {
  local destination="${TEST_TMP}/drift-destination"
  local fake_bin="${TEST_TMP}/drift-bin"
  local ready="${TEST_TMP}/drift-ready"
  local release="${TEST_TMP}/drift-release"
  local install_output="${TEST_TMP}/drift-output"
  local install_status=0 install_pid attempt

  mkdir -p "${destination}/agents" "${destination}/workspace-ceo" "$fake_bin"
  printf 'old shared state\n' > "${destination}/agents/marker.txt"
  printf 'old persona\n' > "${destination}/workspace-ceo/SOUL.md"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    "ready='$ready'" \
    "release='$release'" \
    'if [[ ! -e "$ready" ]]; then' \
    '  : > "$ready"' \
    '  while [[ ! -e "$release" ]]; do sleep 0.02; done' \
    'fi' \
    'exec /bin/cp "$@"' > "${fake_bin}/cp"
  chmod +x "${fake_bin}/cp"

  PATH="${fake_bin}:$PATH" bash "$INSTALLER" --source "$REPO_ROOT" \
    --destination "$destination" --apply ceo > "$install_output" 2>&1 &
  install_pid=$!
  for attempt in $(seq 1 100); do
    [[ -e "$ready" ]] && break
    sleep 0.02
  done
  printf 'user concurrent edit\n' > "${destination}/workspace-ceo/SOUL.md"
  : > "$release"
  wait "$install_pid" || install_status=$?

  if [[ "$install_status" -ne 0 \
     && "$(<"$install_output")" == *"Destination changed after staging began"* \
     && "$(<"${destination}/workspace-ceo/SOUL.md")" == "user concurrent edit" \
     && ! -e "${destination}/workspace-ceo/skills" \
     && ! -e "${TEST_TMP}/.drift-destination.agi-super-team-install.lock" ]]; then
    printf 'ok - destination drift aborts before publish and preserves the concurrent edit\n'
  else
    printf 'not ok - destination drift was overwritten or silently published\n%s\n' "$(<"$install_output")"
    failures=$((failures + 1))
  fi
}

test_destination_drift_aborts_before_publish

test_restore_failure_preserves_recovery_transaction() {
  local destination="${TEST_TMP}/restore-failure-destination"
  local fake_bin="${TEST_TMP}/restore-failure-bin"
  local counter="${TEST_TMP}/restore-failure-count"
  local output status=0 recovery_path

  mkdir -p "${destination}/agents" "${destination}/workspace-ceo" "$fake_bin"
  printf 'old shared state\n' > "${destination}/agents/marker.txt"
  printf 'old persona\n' > "${destination}/workspace-ceo/SOUL.md"
  printf '0\n' > "$counter"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    "counter='$counter'" \
    'count=$(($(cat "$counter") + 1))' \
    'printf "%s\n" "$count" > "$counter"' \
    'if [[ "$count" -ge 4 ]]; then exit 77; fi' \
    'exec /bin/mv "$@"' > "${fake_bin}/mv"
  chmod +x "${fake_bin}/mv"

  output=$(PATH="${fake_bin}:$PATH" bash "$INSTALLER" \
    --source "$REPO_ROOT" --destination "$destination" --apply ceo 2>&1) || status=$?
  recovery_path=$(printf '%s\n' "$output" | sed -n 's/.*Recovery transaction preserved at: //p' | tail -1)

  if [[ "$status" -ne 0 && "$output" == *"automatic restore is incomplete"* \
     && "$output" != *"restored the previous destination state"* \
     && -n "$recovery_path" && -d "$recovery_path" \
     && "$(<"${recovery_path}/backup/agents/marker.txt")" == "old shared state" \
     && "$(<"${recovery_path}/backup/workspace-ceo/SOUL.md")" == "old persona" ]]; then
    printf 'ok - failed automatic restore preserves a named recovery transaction\n'
  else
    printf 'not ok - restore failure deleted backup state or claimed success\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_restore_failure_preserves_recovery_transaction

test_preview_fails_when_a_required_skill_is_missing() {
  local source="${TEST_TMP}/missing-required-source"
  local destination="${TEST_TMP}/missing-required-destination"
  local output status=0 skill

  mkdir -p "${source}/agents/ceo" "${source}/skills"
  write_shared_workspace_files "$source"
  write_ceo_manifest "$source"
  cp "${REPO_ROOT}/agents/ceo/SOUL.md" "${source}/agents/ceo/SOUL.md"
  for skill in context-manager healthcheck web-search project-planner; do
    mkdir -p "${source}/skills/${skill}"
  done

  output=$(bash "$INSTALLER" --source "$source" --destination "$destination" ceo 2>&1) || status=$?
  if [[ "$status" -ne 0 && "$output" == *"Required skill unavailable: team-coordinator"* && ! -e "$destination" ]]; then
    printf 'ok - preview verifies required skills before writing\n'
  else
    printf 'not ok - preview accepted a missing required skill\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_preview_fails_when_a_required_skill_is_missing

test_kit_entrypoint_symlink_fails_before_writes() {
  local source="${TEST_TMP}/entrypoint-symlink-source"
  local destination="${TEST_TMP}/entrypoint-symlink-destination"
  local output status=0

  write_shared_workspace_files "$source"
  write_ceo_manifest "$source"
  mkdir -p "${source}/agents/ceo" "${source}/agents/pe" "${source}/agents/governor" "${source}/skills"
  mv "${source}/starter-kits/fixture-team/RUNBOOK.md" "${source}/starter-kits/fixture-team/RUNBOOK.real.md"
  ln -s RUNBOOK.real.md "${source}/starter-kits/fixture-team/RUNBOOK.md"

  output=$(bash "$INSTALLER" --source "$source" --destination "$destination" \
    --layout coordinated --skill-tier role-only --apply --kit fixture-team 2>&1) || status=$?

  if [[ "$status" -ne 0 && "$output" == *"Kit entrypoint must be a real regular file"* \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - a symlinked kit entrypoint fails before destination writes\n'
  else
    printf 'not ok - a symlinked kit entrypoint was accepted or wrote destination state\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_kit_entrypoint_symlink_fails_before_writes

test_remote_preview_fails_closed_without_a_manifest() {
  local fake_home="${TEST_TMP}/fake-home"
  local fake_bin="${TEST_TMP}/fake-bin"
  local destination="${TEST_TMP}/remote-preview-destination"
  local git_marker="${TEST_TMP}/git-was-called"
  local output status=0

  mkdir -p "$fake_bin"
  printf '#!/usr/bin/env bash\nprintf called > "%s"\nexit 99\n' "$git_marker" > "${fake_bin}/git"
  chmod +x "${fake_bin}/git"

  output=$(HOME="$fake_home" PATH="${fake_bin}:/usr/bin:/bin" bash "$INSTALLER" --destination "$destination" ceo 2>&1) || status=$?
  if [[ "$status" -ne 0 && ! -e "$git_marker" && ! -e "$fake_home" && ! -e "$destination" \
     && "$output" == *"--source"* && "$output" == *"manifest"* \
     && "$output" == *"v1.4.1"* ]]; then
    printf 'ok - remote preview names the pinned ref and does not clone or invent a manifest plan\n'
  else
    printf 'not ok - remote preview invented a plan or touched local state\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_remote_preview_fails_closed_without_a_manifest

test_remote_ref_resolution_failure_does_not_publish() {
  local fake_home="${TEST_TMP}/remote-ref-resolution-home"
  local fake_bin="${TEST_TMP}/remote-ref-resolution-bin"
  local destination="${TEST_TMP}/remote-ref-resolution-destination"
  local output status=0

  mkdir -p "${fake_home}/.agi-super-team/.git" "$fake_bin"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    'case "$*" in' \
    '  *"status --porcelain"*) exit 0 ;;' \
    '  *"fetch --depth 1"*) exit 0 ;;' \
    '  *"rev-parse --verify"*) exit 77 ;;' \
    'esac' \
    'exit 0' > "${fake_bin}/git"
  chmod +x "${fake_bin}/git"

  output=$(HOME="$fake_home" PATH="${fake_bin}:/usr/bin:/bin" bash "$INSTALLER" \
    --destination "$destination" --apply ceo 2>&1) || status=$?

  if [[ "$status" -ne 0 && "$output" == *"Unable to resolve pinned repository ref: v1.4.1"* \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - unresolved remote ref performs zero destination writes\n'
  else
    printf 'not ok - unresolved remote ref continued with unknown source state\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_remote_ref_resolution_failure_does_not_publish

test_remote_checkout_failure_does_not_publish() {
  local fake_home="${TEST_TMP}/remote-checkout-home"
  local fake_bin="${TEST_TMP}/remote-checkout-bin"
  local destination="${TEST_TMP}/remote-checkout-destination"
  local output status=0

  mkdir -p "${fake_home}/.agi-super-team/.git" "$fake_bin"
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    'case "$*" in' \
    '  *"status --porcelain"*) exit 0 ;;' \
    '  *"fetch --depth 1"*) exit 0 ;;' \
    '  *"rev-parse --verify"*) printf "%040d\n" 1; exit 0 ;;' \
    '  *"checkout --detach"*) exit 77 ;;' \
    'esac' \
    'exit 0' > "${fake_bin}/git"
  chmod +x "${fake_bin}/git"

  output=$(HOME="$fake_home" PATH="${fake_bin}:/usr/bin:/bin" bash "$INSTALLER" \
    --destination "$destination" --apply ceo 2>&1) || status=$?

  if [[ "$status" -ne 0 && "$output" == *"Unable to check out pinned repository ref: v1.4.1"* \
     && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - failed pinned checkout performs zero destination writes\n'
  else
    printf 'not ok - failed pinned checkout continued with cached source state\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_remote_checkout_failure_does_not_publish

test_remote_cached_checkout_uses_the_exact_pinned_ref() {
  local fake_home="${TEST_TMP}/remote-pinned-success-home"
  local source="${fake_home}/.agi-super-team"
  local fake_bin="${TEST_TMP}/remote-pinned-success-bin"
  local destination="${TEST_TMP}/remote-pinned-success-destination"
  local git_log="${TEST_TMP}/remote-pinned-success-git.log"
  local output skill

  mkdir -p "${source}/.git" "${source}/agents/ceo" "${source}/skills" "$fake_bin"
  write_shared_workspace_files "$source"
  write_ceo_manifest "$source"
  printf '# CEO\n' > "${source}/agents/ceo/SOUL.md"
  for skill in team-coordinator context-manager healthcheck web-search project-planner; do
    mkdir -p "${source}/skills/${skill}"
    printf '# %s\n' "$skill" > "${source}/skills/${skill}/SKILL.md"
  done
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    "log='$git_log'" \
    'printf "%s\n" "$*" >> "$log"' \
    'case "$*" in' \
    '  *"status --porcelain"*) exit 0 ;;' \
    '  *"fetch --depth 1"*) exit 0 ;;' \
    '  *"rev-parse --verify FETCH_HEAD"*) printf "%s\n" aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa; exit 0 ;;' \
    '  *"checkout --detach --quiet"*) exit 0 ;;' \
    '  *"rev-parse --verify HEAD"*) printf "%s\n" aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa; exit 0 ;;' \
    'esac' \
    'exit 77' > "${fake_bin}/git"
  chmod +x "${fake_bin}/git"

  if ! output=$(HOME="$fake_home" PATH="${fake_bin}:$PATH" bash "$INSTALLER" \
    --destination "$destination" --apply ceo 2>&1); then
    printf 'not ok - exact pinned cached checkout failed\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  if [[ -f "${destination}/workspace-ceo/SOUL.md" \
     && "$(<"$git_log")" == *"fetch --depth 1 https://github.com/aAAaqwq/AGI-Super-Team.git v1.4.1"* \
     && "$(<"$git_log")" == *"checkout --detach --quiet aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"* ]]; then
    printf 'ok - cached remote source fetches and checks out the exact v1.4.1 commit\n'
  else
    printf 'not ok - cached remote source did not use the exact pinned ref\n%s\n' "$(<"$git_log")"
    failures=$((failures + 1))
  fi
}

test_remote_cached_checkout_uses_the_exact_pinned_ref

test_repository_tools_skill_references_resolve() {
  local file skill reference_count=0

  while IFS=$'\t' read -r file skill; do
    reference_count=$((reference_count + 1))
    if [[ ! -f "${REPO_ROOT}/skills/${skill}/SKILL.md" ]]; then
      printf 'not ok - active TOOLS skill reference is unavailable: %s:%s\n' "$file" "$skill"
      failures=$((failures + 1))
      return
    fi
  done < <(perl -nE 'while (/\.\.\/\.\.\/skills\/([A-Za-z0-9._-]+)/g) { say "$ARGV\t$1" }' \
    "${REPO_ROOT}"/agents/*/TOOLS.md | sort -u)

  if [[ "$reference_count" -gt 0 ]] && ! grep -q '/home/' "${REPO_ROOT}"/agents/*/TOOLS.md; then
    printf 'ok - all %s active repository TOOLS skill references resolve\n' "$reference_count"
  else
    printf 'not ok - repository TOOLS references were not fully normalized (count=%s)\n' "$reference_count"
    failures=$((failures + 1))
  fi
}

test_repository_tools_skill_references_resolve

test_removed_skill_links_have_portable_tombstones() {
  local output status=0

  output=$(node - "$REPO_ROOT" <<'NODE'
const fs = require('fs');
const root = process.argv[2];
const file = `${root}/config/external-skill-sources.json`;
const text = fs.readFileSync(file, 'utf8');
const manifest = JSON.parse(text);
if (manifest.schemaVersion !== 1 || manifest.entries.length !== 844) process.exit(1);
if (/\/home\/|\/tmp\//.test(text)) process.exit(2);
for (let index = 0; index < manifest.entries.length; index += 1) {
  const entry = manifest.entries[index];
  if (index && manifest.entries[index - 1].path > entry.path) process.exit(3);
  if (entry.status !== 'unavailable' || entry.reason !== 'non-portable-symlink') process.exit(4);
  if (!['absolute', 'relative'].includes(entry.originalTargetKind)) process.exit(5);
}
process.stdout.write('portable');
NODE
  ) || status=$?

  if [[ "$status" -eq 0 && "$output" == "portable" \
     && "$(find "${REPO_ROOT}/skills" -type l -print -quit)" == "" ]]; then
    printf 'ok - removed skill links have 844 portable tombstone records\n'
  else
    printf 'not ok - skill-link tombstones are incomplete or non-portable\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_removed_skill_links_have_portable_tombstones

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi
