#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

SERVICE_NAME="openclaw-ai-quant-trader.service"

if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
  systemctl --user restart "${SERVICE_NAME}"
  systemctl --user --no-pager -l status "${SERVICE_NAME}" || true
else
  echo "systemd user instance not available; running unified daemon in foreground (paper)."
  cd "${PROJECT_DIR}"
  exec env AI_QUANT_MODE=paper "${PROJECT_DIR}/.venv/bin/python3" -u -m engine.daemon
fi
