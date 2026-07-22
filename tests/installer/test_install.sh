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
  mkdir -p "${source}/config"
  node - "${source}/config/team-manifest.json" "$required" <<'NODE'
const fs = require('fs');
const [path, required] = process.argv.slice(2);
const skills = required.split(/\s+/).filter(Boolean);
fs.writeFileSync(path, JSON.stringify({
  $schema: './team-manifest.schema.json', schemaVersion: 1,
  inventory: {agentCount: 1, physicalSkillCount: 0, skillEntrypoint: 'SKILL.md', symlinkPolicy: 'forbid'},
  agents: [{id: 'ceo', name: 'CEO', path: 'agents/ceo', skills: {
    required: skills, optional: [], harnessSpecific: [], recommendedExternal: []}}],
  kits: [{id: 'ceo', agents: ['ceo']}]
}));
NODE
}

write_full_team_manifest() {
  local source="$1"
  mkdir -p "${source}/config"
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
  agents: ids.map(id => ({id, name: id.toUpperCase(), path: `agents/${id}`, skills: {
    required: assignments[id].split(/\s+/).filter(Boolean), optional: [], harnessSpecific: [], recommendedExternal: []}})),
  kits: [{id: 'full-team', agents: ids}]
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
  assert_file "${destination}/workspace-ceo/skills/brainstorming/SKILL.md"
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
    printf 'ok - full-team classifies 24 legacy skills as recommended external without warnings\n'
  else
    printf 'not ok - full-team emitted normal warnings for recommended external skills\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_full_team_installs_all_agent_directories

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

test_remote_preview_does_not_clone_or_touch_home() {
  local fake_home="${TEST_TMP}/fake-home"
  local fake_bin="${TEST_TMP}/fake-bin"
  local destination="${TEST_TMP}/remote-preview-destination"
  local git_marker="${TEST_TMP}/git-was-called"
  local output status=0

  mkdir -p "$fake_bin"
  printf '#!/usr/bin/env bash\nprintf called > "%s"\nexit 99\n' "$git_marker" > "${fake_bin}/git"
  chmod +x "${fake_bin}/git"

  output=$(HOME="$fake_home" PATH="${fake_bin}:/usr/bin:/bin" bash "$INSTALLER" --destination "$destination" ceo 2>&1) || status=$?
  if [[ "$status" -eq 0 && ! -e "$git_marker" && ! -e "$fake_home" && ! -e "$destination" \
     && "$output" == *"Would clone"* ]]; then
    printf 'ok - remote preview does not clone or touch HOME\n'
  else
    printf 'not ok - remote preview performed or failed a write\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_remote_preview_does_not_clone_or_touch_home

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
