#!/usr/bin/env bash
# Thin wrapper: runs test_docker.sh in online mode.
exec "$(dirname "$0")/test_docker.sh" --online "$@"
