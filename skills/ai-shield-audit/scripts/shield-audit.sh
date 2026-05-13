#!/bin/bash
# Quick audit wrapper for OpenClaw Shield
# Usage: ./scripts/shield-audit.sh [config-path] [--summary|--json]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SHIELD="$SCRIPT_DIR/../bin/shield.js"

CONFIG="${1:-$HOME/.openclaw/openclaw.json}"
FORMAT="${2:---summary}"

exec node "$SHIELD" audit "$CONFIG" "$FORMAT"
