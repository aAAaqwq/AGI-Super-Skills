#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_slidev_common.sh
source "$SCRIPT_DIR/_slidev_common.sh"

usage() {
  cat <<'USAGE'
Usage: slidev-export.sh [entry] [--format pdf|pptx|png|md] [--output file] [--with-clicks] [--range ...] [--dark]

Export Slidev deck.

Arguments:
  entry             Slide entry file (default: slides.md)

Options:
  --format value    pdf|pptx|png|md (default: pdf)
  --output file     Output path
  --with-clicks     Export click steps
  --range value     Slide range, e.g. 1,3-5
  --dark            Export using dark mode
  --install-playwright
                    Install playwright-chromium automatically when missing
  -h, --help        Show help
USAGE
}

entry="slides.md"
format="pdf"
output=""
with_clicks=0
range=""
dark=0
install_playwright=0
has_entry=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --format)
      shift
      [[ $# -gt 0 ]] || { print_error "Missing value for --format"; exit 1; }
      format="$1"
      shift
      ;;
    --output)
      shift
      [[ $# -gt 0 ]] || { print_error "Missing value for --output"; exit 1; }
      output="$1"
      shift
      ;;
    --with-clicks)
      with_clicks=1
      shift
      ;;
    --range)
      shift
      [[ $# -gt 0 ]] || { print_error "Missing value for --range"; exit 1; }
      range="$1"
      shift
      ;;
    --dark)
      dark=1
      shift
      ;;
    --install-playwright)
      install_playwright=1
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

case "$format" in
  pdf|pptx|png|md) ;;
  *)
    print_error "Invalid --format: $format"
    exit 1
    ;;
esac

has_playwright() {
  node -e "require.resolve('playwright-chromium/package.json')" >/dev/null 2>&1
}

if ! has_playwright; then
  if [[ $install_playwright -eq 1 ]]; then
    if ! command -v npm >/dev/null 2>&1; then
      print_error "playwright-chromium is missing and npm is not available to install it"
      exit 1
    fi
    printf 'Installing playwright-chromium...\n' >&2
    npm install -D playwright-chromium >/dev/null
  fi
fi

if ! has_playwright; then
  print_error "playwright-chromium is required for slidev export. Install with: npm i -D playwright-chromium or pass --install-playwright"
  exit 1
fi

if [[ "$format" == "md" ]]; then
  if [[ -z "$output" ]]; then
    entry_base="$(basename "$entry")"
    entry_stem="${entry_base%.*}"
    output="out/${entry_stem}-export.md"
    printf 'Using md export output path: %s\n' "$output" >&2
  elif [[ "$output" != */* ]]; then
    output="out/$output"
    printf 'Adjusted md export output path to avoid Slidev rmdir bug: %s\n' "$output" >&2
  fi
  mkdir -p "$(dirname "$output")"
fi

args=("export" "$entry" "--format" "$format")
[[ -n "$output" ]] && args+=("--output" "$output")
[[ $with_clicks -eq 1 ]] && args+=("--with-clicks")
[[ -n "$range" ]] && args+=("--range" "$range")
[[ $dark -eq 1 ]] && args+=("--dark")

run_slidev "${args[@]}"
