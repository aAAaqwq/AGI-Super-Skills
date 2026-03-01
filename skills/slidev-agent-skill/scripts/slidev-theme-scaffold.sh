#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: slidev-theme-scaffold.sh [theme-name]

Scaffold a local Slidev theme package.

Arguments:
  theme-name     Theme folder name (default: slidev-theme-custom)

Options:
  -h, --help     Show help
USAGE
}

theme_name="slidev-theme-custom"

if [[ $# -gt 0 ]]; then
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    *)
      theme_name="$1"
      shift
      ;;
  esac
fi

if [[ $# -gt 0 ]]; then
  printf 'Error: Unexpected extra arguments\n' >&2
  usage >&2
  exit 1
fi

if [[ -e "$theme_name" ]]; then
  printf 'Error: %s already exists\n' "$theme_name" >&2
  exit 1
fi

mkdir -p "$theme_name/layouts" "$theme_name/styles" "$theme_name/setup"

theme_basename="$(basename "$theme_name")"
pkg_slug="$(printf '%s' "$theme_basename" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g' | sed 's/^-//; s/-$//')"
if [[ -z "$pkg_slug" ]]; then
  pkg_slug="custom"
fi

pkg_name="$pkg_slug"
if [[ "$pkg_name" != slidev-theme-* ]]; then
  pkg_name="slidev-theme-$pkg_name"
fi

cat > "$theme_name/package.json" <<EOF_PKG
{
  "name": "$pkg_name",
  "version": "0.0.1",
  "private": true,
  "type": "module",
  "keywords": ["slidev", "slidev-theme"],
  "slidev": {
    "colorSchema": "both",
    "defaults": {
      "layout": "default"
    }
  }
}
EOF_PKG

cat > "$theme_name/layouts/default.vue" <<'EOF_LAYOUT'
<template>
  <div class="slidev-layout default px-12 py-8">
    <slot />
  </div>
</template>
EOF_LAYOUT

cat > "$theme_name/styles/index.css" <<'EOF_STYLE'
:root {
  --slidev-theme-primary: #2563eb;
}

.slidev-layout {
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
}
EOF_STYLE

cat > "$theme_name/setup/main.ts" <<'EOF_SETUP'
import './styles/index.css'
EOF_SETUP

printf 'Scaffolded local theme at %s\n' "$theme_name"
if [[ "$theme_name" = /* ]]; then
  printf 'Use it in slides headmatter with: theme: %s\n' "$theme_name"
else
  printf 'Use it in slides headmatter with: theme: ./%s\n' "$theme_name"
fi
