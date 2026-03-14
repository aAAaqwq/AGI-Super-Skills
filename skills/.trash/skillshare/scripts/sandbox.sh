#!/usr/bin/env bash
# Unified sandbox management script.
# Usage: ./scripts/sandbox.sh <command>
#
# Commands:
#   up        Start playground container (with demo content)
#   bare      Start playground without auto-init (clean slate)
#   shell     Enter running playground shell
#   down      Stop and remove playground container
#   reset     Stop + remove playground volume (full reset)
#   status    Show playground container status
#   logs      Tail playground container logs
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/_sandbox_common.sh"

usage() {
  echo "Usage: $(basename "$0") <command>"
  echo ""
  echo "Commands:"
  echo "  up        Start playground (with demo content)"
  echo "  bare      Start playground without auto-init"
  echo "  shell     Enter running playground shell"
  echo "  down      Stop and remove playground"
  echo "  reset     Stop + remove volume (full reset)"
  echo "  status    Show container status"
  echo "  logs      Tail container logs"
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

CMD="$1"
shift

case "$CMD" in
  up)
    exec "$SCRIPT_DIR/sandbox_playground_up.sh" "$@"
    ;;
  bare)
    exec "$SCRIPT_DIR/sandbox_playground_up.sh" --bare "$@"
    ;;
  shell)
    exec "$SCRIPT_DIR/sandbox_playground_shell.sh" "$@"
    ;;
  down)
    exec "$SCRIPT_DIR/sandbox_playground_down.sh" "$@"
    ;;
  reset)
    exec "$SCRIPT_DIR/sandbox_playground_down.sh" --volumes "$@"
    ;;
  status)
    require_docker
    cd "$PROJECT_ROOT"
    docker compose -f "$COMPOSE_FILE" --profile playground ps
    ;;
  logs)
    require_docker
    cd "$PROJECT_ROOT"
    docker compose -f "$COMPOSE_FILE" --profile playground logs -f skillshare-playground
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    echo "Error: unknown command '$CMD'" >&2
    echo ""
    usage
    exit 1
    ;;
esac
