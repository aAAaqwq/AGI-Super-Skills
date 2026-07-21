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

test_ceo_uses_canonical_source_and_workspace() {
  local destination="${TEST_TMP}/ceo-destination"
  local output

  if ! output=$(bash "$INSTALLER" --source "$REPO_ROOT" --destination "$destination" --apply ceo 2>&1); then
    printf 'not ok - CEO install failed\n%s\n' "$output"
    failures=$((failures + 1))
    return
  fi

  assert_file "${destination}/workspace-ceo/SOUL.md"
  assert_file "${destination}/workspace-ceo/skills/brainstorming/SKILL.md"
  if ! cmp -s "${REPO_ROOT}/agents/ceo/SOUL.md" "${destination}/workspace-ceo/SOUL.md"; then
    printf 'not ok - CEO persona did not come from agents/ceo\n'
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

test_full_team_preflight_fails_before_any_write() {
  local source="${TEST_TMP}/preflight-source"
  local destination="${TEST_TMP}/preflight-destination"
  local output status=0 agent skill

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
  printf '%s\n' 'test persona' > "${source}/agents/ceo/SOUL.md"
  for skill in team-coordinator context-manager healthcheck web-search project-planner; do
    mkdir -p "${source}/skills/${skill}"
  done
  printf '%s\n' '#!/usr/bin/env sh' 'exit 77' > "${fake_bin}/cp"
  chmod +x "${fake_bin}/cp"

  output=$(PATH="${fake_bin}:/usr/bin:/bin" bash "$INSTALLER" \
    --source "$source" --destination "$destination" --apply ceo 2>&1) || status=$?

  if [[ "$status" -ne 0 && ! -e "$destination" && ! -L "$destination" ]]; then
    printf 'ok - failed staging does not publish a partial workspace\n'
  else
    printf 'not ok - failed staging left destination writes behind\n%s\n' "$output"
    failures=$((failures + 1))
  fi
}

test_failed_staging_does_not_publish_a_partial_workspace

test_preview_fails_when_a_required_skill_is_missing() {
  local source="${TEST_TMP}/missing-required-source"
  local destination="${TEST_TMP}/missing-required-destination"
  local output status=0 skill

  mkdir -p "${source}/agents/ceo" "${source}/skills"
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

  if [[ "$reference_count" -eq 121 ]] && ! grep -q '/home/' "${REPO_ROOT}"/agents/*/TOOLS.md; then
    printf 'ok - all 121 active repository TOOLS skill references resolve\n'
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
