#!/bin/bash
# Production entrypoint: initialise config if missing, then exec CMD.
set -e

if [ ! -f "$HOME/.config/skillshare/config.yaml" ]; then
  echo "First run: initialising skillshare config..."
  skillshare init -g --no-copy --no-git --skill 2>/dev/null || true
fi

exec "$@"
