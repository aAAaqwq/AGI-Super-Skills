#!/usr/bin/env bash
# Enter the running Docker playground or execute a command inside it.
set -euo pipefail

source "$(dirname "$0")/_sandbox_common.sh"
SERVICE="sandbox-playground"

require_docker
cd "$PROJECT_ROOT"

if [[ -z "$(docker compose -f "$COMPOSE_FILE" --profile playground ps -q "$SERVICE")" ]]; then
  echo "Playground is not running. Start it first:"
  echo "  make playground                # start + enter shell (one step)"
  echo "  ./scripts/sandbox.sh up        # start only"
  exit 1
fi

if [[ $# -gt 0 ]]; then
  docker compose -f "$COMPOSE_FILE" --profile playground exec -w /sandbox-home --user "$(id -u):$(id -g)" "$SERVICE" bash -c "$*"
else
  docker compose -f "$COMPOSE_FILE" --profile playground exec -w /sandbox-home --user "$(id -u):$(id -g)" "$SERVICE" bash
fi
