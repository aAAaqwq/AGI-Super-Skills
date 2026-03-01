#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_slidev_common.sh
source "$SCRIPT_DIR/_slidev_common.sh"

usage() {
  cat <<'USAGE'
Usage: slidev-theme-eject.sh [entry] [--dir theme] [--theme name]

Eject active Slidev theme into a local directory.

Arguments:
  entry          Slide entry file (default: slides.md)

Options:
  --dir theme    Output directory for ejected theme (default: theme)
  --theme name   Theme override
  -h, --help     Show help
USAGE
}

entry="slides.md"
dir="theme"
theme=""
has_entry=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --dir)
      shift
      [[ $# -gt 0 ]] || { print_error "Missing value for --dir"; exit 1; }
      dir="$1"
      shift
      ;;
    --theme)
      shift
      [[ $# -gt 0 ]] || { print_error "Missing value for --theme"; exit 1; }
      theme="$1"
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

args=("theme" "eject" "--entry" "$entry" "--dir" "$dir")
[[ -n "$theme" ]] && args+=("--theme" "$theme")

run_slidev "${args[@]}"
