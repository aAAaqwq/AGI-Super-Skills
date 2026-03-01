#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'USAGE'
Usage: slidev-init.sh [dir]

Initialize a Slidev deck directory.

Arguments:
  dir            Target directory (default: current directory)

Options:
  -h, --help     Show this help message
  --no-install   Do not install @slidev/cli
USAGE
}

target_dir="."
install_cli=1
has_target=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --no-install)
      install_cli=0
      shift
      ;;
    *)
      if [[ $has_target -eq 1 ]]; then
        printf 'Error: Unexpected argument: %s\n' "$1" >&2
        usage >&2
        exit 1
      fi
      target_dir="$1"
      has_target=1
      shift
      ;;
  esac
done

mkdir -p "$target_dir"

if [[ ! -f "$target_dir/slides.md" ]]; then
  cat > "$target_dir/slides.md" <<'SLIDES'
---
title: New Slidev Deck
---

# Welcome

Start editing your Slidev presentation.
SLIDES
  printf 'Created %s/slides.md\n' "$target_dir"
else
  printf 'Found existing %s/slides.md\n' "$target_dir"
fi

if [[ ! -f "$target_dir/package.json" ]]; then
  cat > "$target_dir/package.json" <<'PKG'
{
  "name": "slidev-deck",
  "private": true,
  "devDependencies": {
    "@slidev/cli": "^52.0.0",
    "@slidev/theme-default": "^0.25.0"
  },
  "scripts": {
    "dev": "slidev",
    "build": "slidev build",
    "export": "slidev export"
  }
}
PKG
  printf 'Created %s/package.json\n' "$target_dir"
fi

if [[ $install_cli -eq 1 ]]; then
  if command -v npm >/dev/null 2>&1; then
    (
      cd "$target_dir"
      npm install -D @slidev/cli @slidev/theme-default >/dev/null
    )
    printf 'Installed @slidev/cli and @slidev/theme-default in %s\n' "$target_dir"
  else
    printf 'Warning: npm not found, skipped Slidev dependency installation\n' >&2
  fi
fi

printf 'Initialization complete. Start dev server with: %s %s/slides.md\n' "$SCRIPT_DIR/slidev-dev.sh" "$target_dir"
