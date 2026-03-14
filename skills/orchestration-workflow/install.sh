#!/usr/bin/env bash
# ============================================================================
# install.sh — One-command install for orchestration-workflow skill pack
# ============================================================================
# Usage:
#   curl -sL https://raw.githubusercontent.com/Arslan-Z/orchestration-workflow/main/install.sh | bash
#
# Or locally:
#   git clone https://github.com/Arslan-Z/orchestration-workflow.git
#   cd orchestration-workflow && ./install.sh
# ============================================================================

set -euo pipefail

SKILL_DIR="${OPENCLAW_SKILLS_DIR:-${HOME}/.openclaw/skills/orchestration-workflow}"
REPO_URL="https://github.com/Arslan-Z/orchestration-workflow.git"

echo "🔧 Installing orchestration-workflow skill pack..."

# Detect if running from repo or via curl
if [ -f "SKILL.md" ] && [ -d "scripts" ]; then
  SRC="$(pwd)"
  echo "   Installing from local repo: $SRC"
else
  SRC=$(mktemp -d)
  echo "   Cloning from GitHub..."
  git clone --depth 1 "$REPO_URL" "$SRC" 2>/dev/null
fi

# Create target directory
mkdir -p "$SKILL_DIR"

# Copy components
echo "   📄 SKILL.md"
cp "$SRC/SKILL.md" "$SKILL_DIR/"

echo "   📁 scripts/ (6 files)"
mkdir -p "$SKILL_DIR/scripts"
cp "$SRC"/scripts/*.sh "$SKILL_DIR/scripts/"
chmod +x "$SKILL_DIR/scripts/"*.sh

echo "   📁 worker-skills/ (skill fragments)"
mkdir -p "$SKILL_DIR/worker-skills"
cp "$SRC"/worker-skills/*.md "$SKILL_DIR/worker-skills/"

echo "   📁 templates/ (task prompt templates)"
mkdir -p "$SKILL_DIR/templates"
cp "$SRC"/templates/*.md "$SKILL_DIR/templates/"

# Verify
SCRIPTS=$(ls "$SKILL_DIR/scripts/"*.sh 2>/dev/null | wc -l | tr -d ' ')
SKILLS=$(ls "$SKILL_DIR/worker-skills/"*.md 2>/dev/null | wc -l | tr -d ' ')
TEMPLATES=$(ls "$SKILL_DIR/templates/"*.md 2>/dev/null | wc -l | tr -d ' ')

echo ""
echo "✅ Installed to: $SKILL_DIR"
echo "   Scripts:       $SCRIPTS"
echo "   Worker Skills: $SKILLS"
echo "   Templates:     $TEMPLATES"
echo ""
echo "Usage:"
echo "  orchestrate.sh /path/to/repo task-name prompt.md codex --yolo --skills=\"core frontend\""
echo ""
echo "Available skill tags:"
for f in "$SKILL_DIR/worker-skills/"*.md; do
  TAG=$(basename "$f" .md)
  echo "  - $TAG"
done

# ---- Auto-add scripts to PATH ----
SCRIPTS_PATH="$SKILL_DIR/scripts"
PATH_ADDED=0

# Detect shell config file
if [ -n "${ZSH_VERSION:-}" ] || [ -f "$HOME/.zshrc" ]; then
  SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
  SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.bash_profile" ]; then
  SHELL_RC="$HOME/.bash_profile"
elif [ -f "$HOME/.profile" ]; then
  SHELL_RC="$HOME/.profile"
else
  SHELL_RC=""
fi

if [ -n "$SHELL_RC" ]; then
  if ! grep -q "orchestration-workflow/scripts" "$SHELL_RC" 2>/dev/null; then
    echo "" >> "$SHELL_RC"
    echo "# orchestration-workflow scripts" >> "$SHELL_RC"
    echo "export PATH=\"$SCRIPTS_PATH:\$PATH\"" >> "$SHELL_RC"
    PATH_ADDED=1
    echo ""
    echo "✅ PATH added to $SHELL_RC"
    echo "   Run: source $SHELL_RC  (or open new terminal)"
  else
    echo ""
    echo "✅ PATH already configured in $SHELL_RC"
  fi
fi

# Also symlink to ~/.local/bin as fallback
if [ -d "$HOME/.local/bin" ] || mkdir -p "$HOME/.local/bin" 2>/dev/null; then
  for script in "$SCRIPTS_PATH"/*.sh; do
    BASENAME=$(basename "$script")
    ln -sf "$script" "$HOME/.local/bin/$BASENAME" 2>/dev/null || true
  done
  echo "✅ Symlinked scripts to ~/.local/bin/"
fi

# Self-check: verify all dependencies are reachable
echo ""
echo "🔍 Self-check..."
ALL_OK=1
for dep in orchestrate.sh worker-session.sh deploy-verify.sh parse-worker-output.sh inject-worker-skills.sh; do
  if [ -x "$SCRIPTS_PATH/$dep" ]; then
    echo "   ✅ $dep"
  else
    echo "   ❌ $dep MISSING"
    ALL_OK=0
  fi
done

# Check external dependencies
for ext_dep in git tmux npm; do
  if command -v "$ext_dep" &>/dev/null; then
    echo "   ✅ $ext_dep ($(command -v $ext_dep))"
  else
    echo "   ⚠️  $ext_dep not found (optional but recommended)"
  fi
done

# Check codex/claude availability
AGENTS_FOUND=0
for agent in codex claude; do
  if command -v "$agent" &>/dev/null; then
    echo "   ✅ $agent agent available"
    AGENTS_FOUND=$((AGENTS_FOUND + 1))
  fi
done
[ "$AGENTS_FOUND" -eq 0 ] && echo "   ⚠️  No coding agents found (install codex or claude)"

if [ "$ALL_OK" -eq 1 ]; then
  echo ""
  echo "🎉 All checks passed. Ready to orchestrate!"
else
  echo ""
  echo "⚠️  Some scripts missing. Try reinstalling."
fi
