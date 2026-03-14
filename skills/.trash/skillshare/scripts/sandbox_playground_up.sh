#!/usr/bin/env bash
# Start a persistent Docker playground for interactive skillshare usage.
# Usage: ./sandbox_playground_up.sh [--bare]
#   --bare  Skip auto-init and demo setup (clean slate for manual testing)
set -euo pipefail

source "$(dirname "$0")/_sandbox_common.sh"
SERVICE="sandbox-playground"

BARE=false
for arg in "$@"; do
  case "$arg" in
    --bare) BARE=true ;;
  esac
done

require_docker
cd "$PROJECT_ROOT"

# Resolve GitHub token from env vars or gh CLI (for search command inside playground).
SKILLSHARE_PLAYGROUND_GITHUB_TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
if [ -z "$SKILLSHARE_PLAYGROUND_GITHUB_TOKEN" ] && command -v gh &>/dev/null; then
  SKILLSHARE_PLAYGROUND_GITHUB_TOKEN="$(gh auth token 2>/dev/null || true)"
fi
export SKILLSHARE_PLAYGROUND_GITHUB_TOKEN

docker compose -f "$COMPOSE_FILE" --profile playground build "$SERVICE"

# Prepare shared volumes for host UID/GID access.
docker compose -f "$COMPOSE_FILE" --profile playground run --rm --user "0:0" --cap-add ALL "$SERVICE" \
  bash -c "mkdir -p /go/pkg/mod /go/build-cache /sandbox-home /tmp && chmod -R 0777 /go/pkg/mod /go/build-cache /sandbox-home /tmp"

docker compose -f "$COMPOSE_FILE" --profile playground up -d "$SERVICE"

# Build skillshare binary and set up aliases.
docker compose -f "$COMPOSE_FILE" --profile playground exec --user "$(id -u):$(id -g)" "$SERVICE" \
  bash -c '
    mkdir -p /sandbox-home/.local/bin
    go build -o /sandbox-home/.local/bin/skillshare ./cmd/skillshare
    ln -sf /sandbox-home/.local/bin/skillshare /sandbox-home/.local/bin/ss
    touch /sandbox-home/.bashrc
    grep -qxF "alias ss='"'"'skillshare'"'"'" /sandbox-home/.bashrc || echo "alias ss='"'"'skillshare'"'"'" >> /sandbox-home/.bashrc
    grep -qxF "alias skillshare-ui='"'"'skillshare ui -g --host 0.0.0.0 --no-open'"'"'" /sandbox-home/.bashrc || echo "alias skillshare-ui='"'"'skillshare ui -g --host 0.0.0.0 --no-open'"'"'" >> /sandbox-home/.bashrc
    grep -qxF "alias skillshare-ui-p='"'"'cd /sandbox-home/demo-project && skillshare ui -p --host 0.0.0.0 --no-open'"'"'" /sandbox-home/.bashrc || echo "alias skillshare-ui-p='"'"'cd /sandbox-home/demo-project && skillshare ui -p --host 0.0.0.0 --no-open'"'"'" >> /sandbox-home/.bashrc
  '

if [ "$BARE" = true ]; then
  # --bare: only create target directories so the binary can detect them
  docker compose -f "$COMPOSE_FILE" --profile playground exec --user "$(id -u):$(id -g)" "$SERVICE" \
    bash -c 'mkdir -p /sandbox-home/.claude/skills'
else

# Initialize global mode (needed for skillshare-ui alias).
docker compose -f "$COMPOSE_FILE" --profile playground exec --user "$(id -u):$(id -g)" "$SERVICE" \
  bash -c '
    if [ ! -f /sandbox-home/.config/skillshare/config.yaml ]; then
      mkdir -p /sandbox-home/.claude/skills
      skillshare init -g --no-copy --all-targets --no-git --skill
    fi
  '

# Create demo content (shared script).
docker compose -f "$COMPOSE_FILE" --profile playground exec --user "$(id -u):$(id -g)" "$SERVICE" \
  bash -c '/workspace/scripts/create-demo-content.sh \
    /sandbox-home/.config/skillshare/skills \
    /sandbox-home/.config/skillshare \
    /sandbox-home/demo-project'

fi  # end of if [ "$BARE" != true ]

echo "══════════════════════════════════════════════════════════"
if [ "$BARE" = true ]; then
echo "  Playground is running! (bare mode — no auto-init)"
else
echo "  Playground is running!"
fi
echo "  Enter with:  ./scripts/sandbox.sh shell   (or 'make playground' for one step)"
echo "══════════════════════════════════════════════════════════"
echo ""
echo "Available commands: skillshare (alias: ss)"
echo ""
if [ "$BARE" = true ]; then
echo "Bare mode — run 'ss init' manually to get started."
else
echo "Quick start (global mode — ready to use):"
echo "  skillshare status       # check current state"
echo "  skillshare list         # see flat + nested skills"
echo "  skillshare-ui           # start web dashboard (port 19420)"
echo ""
echo "Quick start (project mode — ready to use):"
echo "  cd ~/demo-project       # pre-configured demo project"
echo "  skillshare status       # auto-detects project mode"
echo "  skillshare-ui-p         # project mode web dashboard (port 19420)"
echo ""
echo "Nested skills (--into demo, pre-loaded):"
echo "  ls ~/.config/skillshare/skills/security/  # nested audit skills"
echo "  ls ~/.config/skillshare/skills/devops/     # nested devops skills"
echo "  skillshare install ~/some-skill --into frontend  # install into subdir"
echo ""
echo "Audit playground (pre-loaded with demo skills):"
echo "  skillshare audit        # scan all skills, see findings"
echo "  cat ~/.config/skillshare/audit-rules.yaml  # inspect global rules"
echo "  skillshare-ui           # web dashboard → Audit & Audit Rules pages"
echo ""
echo "Try audit in project mode:"
echo "  cd ~/demo-project"
echo "  skillshare audit        # project-level scan with custom rules"
echo "  cat .skillshare/audit-rules.yaml           # inspect project rules"
fi
echo ""
if [ -n "$SKILLSHARE_PLAYGROUND_GITHUB_TOKEN" ]; then
  echo "GitHub token: detected (search command will work)"
else
  echo "GitHub token: not set (export GITHUB_TOKEN=... to enable 'skillshare search')"
fi
