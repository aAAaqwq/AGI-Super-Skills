#!/bin/bash
# Setup script for multi-agent content team

set -e

if [ $# -lt 2 ]; then
  echo "Usage: ./setup-team.sh <writer-id> <role-1> [role-2] ..."
  echo "Example: ./setup-team.sh my-writer fact-reviewer style-reviewer scorer fixer"
  exit 1
fi

WRITER_ID=$1
shift
OTHER_ROLES=("$@")

BASE_DIR="$HOME/.openclaw"
WRITER_WS="$BASE_DIR/workspace-$WRITER_ID"

echo "=== Creating writer workspace: $WRITER_ID ==="
mkdir -p "$WRITER_WS/OUTPUT" "$WRITER_WS/KNOWLEDGE"

cat > "$WRITER_WS/TOOLS.md" << 'EOF'
# TOOLS.md - Writer

## Critical Reminders
1. Do NOT read AGENTS.md — auto-injected into context
2. Always provide `path` parameter for read/write
3. Tool calls must include all required parameters

## Working Directory
- workspace: workspace-writer/
- output: OUTPUT/{project}/
- knowledge: KNOWLEDGE/
EOF

echo "✓ Writer workspace created"

for role in "${OTHER_ROLES[@]}"; do
  echo "=== Creating shell workspace: $role ==="
  SHELL_WS="$BASE_DIR/workspace-$role"
  
  mkdir -p "$SHELL_WS"
  
  # Create absolute path symlinks
  ln -sf "$WRITER_WS/OUTPUT" "$SHELL_WS/OUTPUT"
  ln -sf "$WRITER_WS/KNOWLEDGE" "$SHELL_WS/KNOWLEDGE"
  
  cat > "$SHELL_WS/TOOLS.md" << EOF
# TOOLS.md - $role

## Critical Reminders
1. Do NOT read AGENTS.md — auto-injected into context
2. Always provide \`path\` parameter for read/write
3. Tool calls must include all required parameters

## Working Directory
- workspace: workspace-$role/
- OUTPUT/ → workspace-$WRITER_ID/OUTPUT/ (symlink)
- KNOWLEDGE/ → workspace-$WRITER_ID/KNOWLEDGE/ (symlink)
EOF
  
  echo "✓ $role workspace created"
done

echo ""
echo "=== Add to openclaw.json ==="
echo '{'
echo '  "agents": {'
echo '    "list": ['
echo "      {\"id\": \"$WRITER_ID\", \"workspace\": \"~/.openclaw/workspace-$WRITER_ID\"},"
for role in "${OTHER_ROLES[@]}"; do
  echo "      {\"id\": \"$role\", \"workspace\": \"~/.openclaw/workspace-$role\"},"
done
echo '      ...'
echo '    ],'
echo '    "defaults": { ... }'
echo '  }'
echo '}'
echo ""
echo "=== Add to main agent allowAgents ==="
echo '"subagents": {'
echo '  "allowAgents": ['
echo "    \"$WRITER_ID\","
for role in "${OTHER_ROLES[@]}"; do
  echo "    \"$role\","
done
echo '    ...'
echo '  ]'
echo '}'
echo ""
echo "✓ Setup complete!"