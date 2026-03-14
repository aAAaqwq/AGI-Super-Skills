#!/bin/bash
# bootstrap.sh — New Mac Claude Code workflow setup (<15 min)
# Usage: bash bootstrap.sh
# Source: vault/40-49 Agents/Workflows/claude-code/templates/bootstrap.sh

set -e
VAULT="$HOME/Documents/Obsidian/My-Second-Brain-2.0"
CLAUDE_CODE_DIR="$VAULT/40-49 Agents/Workflows/claude-code"

echo "=== Claude Code Workflow Bootstrap ==="

# Step 1: Core tools
echo "[1/4] Installing core tools..."
brew install node uv gh ffmpeg 2>/dev/null || true
npm install -g @anthropic-ai/claude-code bmalph gitnexus

# Step 2: Python tools
echo "[2/4] Installing Python tools..."
uv tool install claude-monitor 2>/dev/null || echo "claude-monitor: check manually"

# Step 3: Claude Code plugins + skills
echo "[3/4] Setting up Claude Code..."
# Copy global CLAUDE.md template
mkdir -p ~/.claude
cp "$CLAUDE_CODE_DIR/templates/CLAUDE.md" ~/.claude/CLAUDE.md.template
echo "→ CLAUDE.md template at ~/.claude/CLAUDE.md.template (customize per project)"

# Step 4: MCP config
echo "[4/4] Configuring MCP..."
# GitNexus MCP is configured via claude settings
# Run in project dir: npx gitnexus analyze

echo ""
echo "=== Setup complete ==="
echo "Next: Open Claude Code, paste the init prompt from:"
echo "  $CLAUDE_CODE_DIR/README.md"
echo ""
echo "Current quick-ref:"
cat "$CLAUDE_CODE_DIR/quick-ref.md" 2>/dev/null | head -20 || echo "(run from machine with vault access)"
