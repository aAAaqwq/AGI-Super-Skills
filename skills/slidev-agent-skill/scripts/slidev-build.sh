#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_slidev_common.sh
source "$SCRIPT_DIR/_slidev_common.sh"

usage() {
  cat <<'USAGE'
Usage: slidev-build.sh [entry] [--out dir] [--base /x/] [--without-notes]

Build Slidev deck as SPA.

Arguments:
  entry             Slide entry file (default: slides.md)

Options:
  --out dir         Output directory
  --base /x/        Base path
  --without-notes   Exclude speaker notes
  -h, --help        Show help
USAGE
}

entry="slides.md"
out=""
base=""
without_notes=0
has_entry=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --out)
      shift
      [[ $# -gt 0 ]] || { print_error "Missing value for --out"; exit 1; }
      out="$1"
      shift
      ;;
    --base)
      shift
      [[ $# -gt 0 ]] || { print_error "Missing value for --base"; exit 1; }
      base="$1"
      shift
      ;;
    --without-notes)
      without_notes=1
      shift
      ;;
    *)
      if [[ $has_entry -eq 1 ]]; then
        print_error "Unexpected argument: $1"
        usage >&2
        exit 1
      fi
      entry="$1"
      has_entry=1
      shift
      ;;
  esac
done

args=("build" "$entry")
[[ -n "$out" ]] && args+=("--out" "$out")
[[ -n "$base" ]] && args+=("--base" "$base")
[[ $without_notes -eq 1 ]] && args+=("--without-notes")

run_slidev "${args[@]}"
