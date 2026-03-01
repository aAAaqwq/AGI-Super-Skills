#!/usr/bin/env bash
set -euo pipefail

die() {
  echo "ERROR: $*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage: tools/release/set_version.sh <version>

Example:
  tools/release/set_version.sh 0.1.1
USAGE
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

version="$1"
[[ "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "Version must match SemVer X.Y.Z (got '${version}')"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
version_file="${repo_root}/VERSION"
pyproject_file="${repo_root}/pyproject.toml"
crates_root="${repo_root}/backtester/crates"

printf '%s\n' "${version}" > "${version_file}"
sed -E -i "0,/^version = \".*\"/s//version = \"${version}\"/" "${pyproject_file}"

mapfile -t cargo_tomls < <(find "${crates_root}" -mindepth 2 -maxdepth 2 -type f -name Cargo.toml | sort)
(( ${#cargo_tomls[@]} > 0 )) || die "No crate Cargo.toml files found under ${crates_root}"

for cargo_toml in "${cargo_tomls[@]}"; do
  sed -E -i "0,/^version = \".*\"/s//version = \"${version}\"/" "${cargo_toml}"
done

"${repo_root}/tools/release/check_versions.sh"
echo "Version updated to ${version}."
