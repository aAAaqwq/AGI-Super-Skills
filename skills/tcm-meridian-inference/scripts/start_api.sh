#!/usr/bin/env bash
# TCM Meridian Inference API - One-command start
# Usage: bash scripts/start_api.sh [port]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${1:-${TCM_API_PORT:-18790}}"

export TCM_API_PORT="$PORT"

echo "Starting TCM Meridian Inference API on port $PORT ..."
echo "  Project dir: $PROJECT_DIR"
echo "  Rules dir:   $PROJECT_DIR/rules"
echo ""
echo "Endpoints:"
echo "  POST /api/inference/meridian-diagnosis  — Full inference"
echo "  POST /test                               — Test with sample data"
echo "  GET  /healthz                            — Health check"
echo ""

cd "$SCRIPT_DIR"
exec python3 tcm_api.py
