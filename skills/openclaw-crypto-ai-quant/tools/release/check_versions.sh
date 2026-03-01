#!/usr/bin/env bash
set -euo pipefail

die() {
  echo "ERROR: $*" >&2
  exit 1
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
version_file="${repo_root}/VERSION"
pyproject_file="${repo_root}/pyproject.toml"
crates_root="${repo_root}/backtester/crates"

[[ -f "${version_file}" ]] || die "Missing VERSION file at ${version_file}"
[[ -f "${pyproject_file}" ]] || die "Missing pyproject.toml at ${pyproject_file}"
[[ -d "${crates_root}" ]] || die "Missing crates directory at ${crates_root}"

version="$(tr -d '[:space:]' < "${version_file}")"
[[ "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "VERSION must match SemVer X.Y.Z (got '${version}')"

pyproject_version="$(awk -F'"' '/^version = "/ { print $2; exit }' "${pyproject_file}")"
[[ -n "${pyproject_version}" ]] || die "Cannot parse version from ${pyproject_file}"
[[ "${pyproject_version}" == "${version}" ]] || die "pyproject version '${pyproject_version}' != VERSION '${version}'"

mapfile -t cargo_tomls < <(find "${crates_root}" -mindepth 2 -maxdepth 2 -type f -name Cargo.toml | sort)
(( ${#cargo_tomls[@]} > 0 )) || die "No crate Cargo.toml files found under ${crates_root}"

for cargo_toml in "${cargo_tomls[@]}"; do
  crate_version="$(awk -F'"' '/^version = "/ { print $2; exit }' "${cargo_toml}")"
  [[ -n "${crate_version}" ]] || die "Cannot parse crate version from ${cargo_toml}"
  [[ "${crate_version}" == "${version}" ]] || die "Crate version '${crate_version}' != VERSION '${version}' in ${cargo_toml}"
done

if [[ "${GITHUB_REF_TYPE:-}" == "tag" ]]; then
  tag_name="${GITHUB_REF_NAME:-}"
  [[ "${tag_name}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "Tag '${tag_name}' must match vX.Y.Z"
  [[ "${tag_name#v}" == "${version}" ]] || die "Tag '${tag_name}' != VERSION '${version}'"
fi

if git -C "${repo_root}" describe --tags --exact-match >/dev/null 2>&1; then
  head_tag="$(git -C "${repo_root}" describe --tags --exact-match)"
  if [[ "${head_tag}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    [[ "${head_tag#v}" == "${version}" ]] || die "HEAD tag '${head_tag}' != VERSION '${version}'"
  fi
fi

echo "Version governance check passed for ${version}."
