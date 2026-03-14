#!/bin/bash
# Install claude-skills: create symlinks from ~/.claude/skills/ to this repo

set -e

SKILLS_DIR="$(cd "$(dirname "$0")/.." && pwd)/skills"
TARGET_DIR="$HOME/.claude/skills"

echo "Claude Skills Installer"
echo "======================"
echo ""
echo "Source: $SKILLS_DIR"
echo "Target: $TARGET_DIR"
echo ""

# Create target directory
mkdir -p "$TARGET_DIR"

# Count skills
SKILL_COUNT=0
LINK_COUNT=0
SKIP_COUNT=0

# Find all SKILL.md files and create symlinks
for skill_dir in "$SKILLS_DIR"/*/SKILL.md "$SKILLS_DIR"/*/*/SKILL.md; do
    # Skip if no match (glob didn't expand)
    [ -f "$skill_dir" ] || continue

    # Get the skill directory (parent of SKILL.md)
    dir="$(dirname "$skill_dir")"
    skill_name="$(basename "$dir")"

    SKILL_COUNT=$((SKILL_COUNT + 1))

    # Skip if symlink already exists and points to the right place
    if [ -L "$TARGET_DIR/$skill_name" ]; then
        existing_target="$(readlink "$TARGET_DIR/$skill_name")"
        if [ "$existing_target" = "$dir" ]; then
            SKIP_COUNT=$((SKIP_COUNT + 1))
            continue
        fi
        # Remove stale symlink
        rm "$TARGET_DIR/$skill_name"
    fi

    # Create symlink
    ln -s "$dir" "$TARGET_DIR/$skill_name"
    echo "  + $skill_name -> $dir"
    LINK_COUNT=$((LINK_COUNT + 1))
done

echo ""
echo "Done!"
echo "  Total skills: $SKILL_COUNT"
echo "  New links:    $LINK_COUNT"
echo "  Already set:  $SKIP_COUNT"
echo ""

# Check for config
CONFIG_FILE="$(dirname "$0")/config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Note: No config.yaml found."
    echo "  Copy config.example.yaml to config.yaml and edit with your paths:"
    echo "  cp setup/config.example.yaml setup/config.yaml"
fi
