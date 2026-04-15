#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <skill-dir-or-SKILL.md>"
  exit 1
fi

target="$1"

if ! command -v tessl >/dev/null 2>&1; then
  cat <<'EOF'
[tessl-skill-review] Tessl CLI is not installed.

Install:
  curl -fsSL https://get.tessl.io | sh

Then inspect CLI if needed:
  tessl --help
  tessl skill --help

Recommended review command:
  tessl skill review <path>
EOF
  exit 2
fi

echo "[tessl-skill-review] Running: tessl skill review $target" >&2
exec tessl skill review "$target"
