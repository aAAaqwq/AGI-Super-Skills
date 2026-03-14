#!/usr/bin/env bash
set -euo pipefail

REPO="jiangmuran/clawguard"
ASSET_URL="https://github.com/${REPO}/releases/latest/download/clawguard.tar.gz"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required (18+)."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required."
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "Downloading latest Clawguard release..."
if ! curl -fsSL "$ASSET_URL" -o "$TMP_DIR/clawguard.tar.gz"; then
  echo "Release asset not found. Falling back to git clone."
  if ! command -v git >/dev/null 2>&1; then
    echo "git is required for fallback install."
    exit 1
  fi
  git clone "https://github.com/${REPO}.git" "$TMP_DIR/clawguard"
  cd "$TMP_DIR/clawguard"
else
  tar -xzf "$TMP_DIR/clawguard.tar.gz" -C "$TMP_DIR"
  cd "$TMP_DIR"
fi

echo "Installing Clawguard..."
npm install -g .

echo "Done. Run: clawguard --help"
