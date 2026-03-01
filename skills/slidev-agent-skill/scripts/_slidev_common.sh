#!/usr/bin/env bash
set -euo pipefail

SLIDEV_CMD=()

print_error() {
  printf 'Error: %s\n' "$1" >&2
}

resolve_slidev_cmd() {
  if [[ -x "./node_modules/.bin/slidev" ]]; then
    SLIDEV_CMD=("./node_modules/.bin/slidev")
    return 0
  fi

  if command -v slidev >/dev/null 2>&1; then
    SLIDEV_CMD=("slidev")
    return 0
  fi

  if command -v npx >/dev/null 2>&1; then
    SLIDEV_CMD=("npx" "-y" "@slidev/cli")
    return 0
  fi

  print_error "Could not find Slidev CLI. Install @slidev/cli or ensure slidev is on PATH."
  return 1
}

run_slidev() {
  resolve_slidev_cmd
  "${SLIDEV_CMD[@]}" "$@"
}
