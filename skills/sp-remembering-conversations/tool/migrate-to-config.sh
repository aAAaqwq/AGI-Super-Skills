#!/usr/bin/env bash
# Migrate conversation archive and index from ~/.clank to ~/.config/superpowers
#
# IMPORTANT: This preserves all data. The old ~/.clank directory is not deleted,
# allowing you to verify the migration before removing it manually.

set -euo pipefail

# Determine target directory
SUPERPOWERS_DIR="${PERSONAL_SUPERPOWERS_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/superpowers}"

OLD_ARCHIVE="$HOME/.clank/conversation-archive"
OLD_INDEX="$HOME/.clank/conversation-index"

NEW_ARCHIVE="${SUPERPOWERS_DIR}/conversation-archive"
NEW_INDEX="${SUPERPOWERS_DIR}/conversation-index"

echo "Migration: ~/.clank → ${SUPERPOWERS_DIR}"
echo ""

# Check if source exists
if [[ ! -d "$HOME/.clank" ]]; then
    echo "✅ No ~/.clank directory found. Nothing to migrate."
    exit 0
fi

# Check if already migrated
if [[ -d "$NEW_ARCHIVE" ]] || [[ -d "$NEW_INDEX" ]]; then
    echo "⚠️  Destination already exists:"
    [[ -d "$NEW_ARCHIVE" ]] && echo "  - ${NEW_ARCHIVE}"
    [[ -d "$NEW_INDEX" ]] && echo "  - ${NEW_INDEX}"
    echo ""
    echo "Migration appears to have already run."
    echo "To re-run migration, manually remove destination directories first."
    exit 1
fi

# Show what will be migrated
echo "Source directories:"
if [[ -d "$OLD_ARCHIVE" ]]; then
    archive_size=$(du -sh "$OLD_ARCHIVE" | cut -f1)
    archive_count=$(find "$OLD_ARCHIVE" -name "*.jsonl" | wc -l | tr -d ' ')
    echo "  Archive: ${OLD_ARCHIVE} (${archive_count} conversations, ${archive_size})"
else
    echo "  Archive: Not found"
fi

if [[ -d "$OLD_INDEX" ]]; then
    index_size=$(du -sh "$OLD_INDEX" | cut -f1)
    echo "  Index: ${OLD_INDEX} (${index_size})"
else
    echo "  Index: Not found"
fi

echo ""
echo "Destination: ${SUPERPOWERS_DIR}"
echo ""

# Confirm
read -p "Proceed with migration? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled."
    exit 0
fi

# Ensure destination base exists
mkdir -p "${SUPERPOWERS_DIR}"

# Migrate archive
if [[ -d "$OLD_ARCHIVE" ]]; then
    echo "Copying conversation archive..."
    cp -r "$OLD_ARCHIVE" "$NEW_ARCHIVE"
    echo "  ✓ Archive migrated"
fi

# Migrate index
if [[ -d "$OLD_INDEX" ]]; then
    echo "Copying conversation index..."
    cp -r "$OLD_INDEX" "$NEW_INDEX"
    echo "  ✓ Index migrated"
fi

# Update database paths to point to new location
if [[ -f "$NEW_INDEX/db.sqlite" ]]; then
    echo "Updating database paths..."
    sqlite3 "$NEW_INDEX/db.sqlite" "UPDATE exchanges SET archive_path = REPLACE(archive_path, '/.clank/', '/.config/superpowers/') WHERE archive_path LIKE '%/.clank/%';"
    echo "  ✓ Database paths updated"
fi

# Verify migration
echo ""
echo "Verifying migration..."

if [[ -d "$OLD_ARCHIVE" ]]; then
    old_count=$(find "$OLD_ARCHIVE" -name "*.jsonl" | wc -l | tr -d ' ')
    new_count=$(find "$NEW_ARCHIVE" -name "*.jsonl" | wc -l | tr -d ' ')

    if [[ "$old_count" -eq "$new_count" ]]; then
        echo "  ✓ All $new_count conversations migrated"
    else
        echo "  ⚠️  Conversation count mismatch: old=$old_count, new=$new_count"
        exit 1
    fi
fi

if [[ -f "$OLD_INDEX/db.sqlite" ]]; then
    old_size=$(stat -f%z "$OLD_INDEX/db.sqlite" 2>/dev/null || stat --format=%s "$OLD_INDEX/db.sqlite" 2>/dev/null)
    new_size=$(stat -f%z "$NEW_INDEX/db.sqlite" 2>/dev/null || stat --format=%s "$NEW_INDEX/db.sqlite" 2>/dev/null)
    echo "  ✓ Database migrated (${new_size} bytes)"
fi

echo ""
echo "✅ Migration complete!"
echo ""
echo "Next steps:"
echo "  1. Test search: ./search-conversations 'test query'"
echo "  2. Verify results look correct"
echo "  3. Once verified, manually remove old directory:"
echo "     rm -rf ~/.clank"
echo ""
echo "The old ~/.clank directory is preserved for safety."

exit 0
