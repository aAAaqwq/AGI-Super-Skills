#!/usr/bin/env bash
set -euo pipefail

die() {
  echo "ERROR: $*" >&2
  exit 1
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
default_version="$(tr -d '[:space:]' < "${repo_root}/VERSION")"
version="${1:-${default_version}}"
output_dir="${2:-${repo_root}/artifacts/releases/v${version}}"

[[ "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "Version must match SemVer X.Y.Z (got '${version}')"

"${repo_root}/tools/release/check_versions.sh"
mkdir -p "${output_dir}"

echo "Building bt-cli release binary..."
cargo build --release -p bt-cli --manifest-path "${repo_root}/backtester/Cargo.toml"

binary_path="${repo_root}/backtester/target/release/mei-backtester"
[[ -x "${binary_path}" ]] || die "Missing release binary at ${binary_path}"
install -m 0755 "${binary_path}" "${output_dir}/mei-backtester-linux-x86_64-v${version}"

mapfile -t config_examples < <(
  cd "${repo_root}"
  find config -maxdepth 1 -type f \( -name "*.example" -o -name "*.example.*" -o -name "*.yaml.example" -o -name "*.yml.example" \) | sort
)
(( ${#config_examples[@]} > 0 )) || die "No config example files found"
tar -C "${repo_root}" -czf "${output_dir}/config-examples-v${version}.tar.gz" "${config_examples[@]}"

mapfile -t systemd_examples < <(
  cd "${repo_root}"
  find systemd -maxdepth 1 -type f -name "*.example" | sort
)
(( ${#systemd_examples[@]} > 0 )) || die "No systemd example files found"
tar -C "${repo_root}" -czf "${output_dir}/systemd-examples-v${version}.tar.gz" "${systemd_examples[@]}"

cat > "${output_dir}/release-manifest-v${version}.txt" <<EOF
version=${version}
git_sha=$(git -C "${repo_root}" rev-parse --short=12 HEAD)
built_at_utc=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF

(
  cd "${output_dir}"
  find . -maxdepth 1 -type f ! -name "SHA256SUMS" -printf '%f\n' | sort | xargs sha256sum > SHA256SUMS
)

echo "Release assets built at ${output_dir}:"
find "${output_dir}" -maxdepth 1 -type f | sort
