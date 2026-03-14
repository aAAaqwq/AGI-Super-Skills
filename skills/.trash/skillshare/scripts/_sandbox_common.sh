#!/usr/bin/env bash
# Shared boilerplate for Docker sandbox scripts.
# Source this file: source "$(dirname "$0")/_sandbox_common.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.sandbox.yml"

# Minimum supported Docker Compose version (v2.20+ for YAML anchors + profiles)
MIN_COMPOSE_VERSION="2.20"

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker command not found" >&2
    case "$(uname -s)" in
      Darwin) echo "Install: brew install --cask docker" >&2 ;;
      Linux)  echo "Install: https://docs.docker.com/engine/install/" >&2 ;;
    esac
    exit 1
  fi

  if ! docker compose version >/dev/null 2>&1; then
    echo "Error: docker compose plugin not available" >&2
    echo "Docker Compose v2 is required (bundled with Docker Desktop)." >&2
    exit 1
  fi

  # Check minimum version
  local compose_ver
  compose_ver="$(docker compose version --short 2>/dev/null | sed 's/^v//')"
  if [[ -n "$compose_ver" ]]; then
    local major minor
    major="${compose_ver%%.*}"
    minor="${compose_ver#*.}"; minor="${minor%%.*}"
    local min_major="${MIN_COMPOSE_VERSION%%.*}"
    local min_minor="${MIN_COMPOSE_VERSION#*.}"; min_minor="${min_minor%%.*}"
    if [[ "$major" -lt "$min_major" ]] || { [[ "$major" -eq "$min_major" ]] && [[ "$minor" -lt "$min_minor" ]]; }; then
      echo "Error: Docker Compose v${compose_ver} is too old (need >= v${MIN_COMPOSE_VERSION})" >&2
      echo "Update Docker Desktop or install a newer compose plugin." >&2
      exit 1
    fi
  fi
}
