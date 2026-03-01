#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_slidev_common.sh
source "$SCRIPT_DIR/_slidev_common.sh"

usage() {
  cat <<'USAGE'
Usage: slidev-dev.sh [entry] [--port N] [--base /x/] [--theme name]

Start Slidev dev server.

Arguments:
  entry          Slide entry file (default: slides.md)

Options:
  --port N       Port number
  --base /x/     Base path
  --theme name   Theme override
  -h, --help     Show help
USAGE
}

entry="slides.md"
port=""
base=""
theme=""
has_entry=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --port)
      shift
      [[ $# -gt 0 ]] || { print_error "Missing value for --port"; exit 1; }
      port="$1"
      shift
      ;;
    --base)
      shift
      [[ $# -gt 0 ]] || { print_error "Missing value for --base"; exit 1; }
      base="$1"
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

args=("$entry")
[[ -n "$port" ]] && args+=("--port" "$port")
[[ -n "$base" ]] && args+=("--base" "$base")
[[ -n "$theme" ]] && args+=("--theme" "$theme")

run_slidev "${args[@]}"
