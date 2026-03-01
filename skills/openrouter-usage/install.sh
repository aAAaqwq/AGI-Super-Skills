#!/bin/bash
set -euo pipefail

# ── openrouter-usage installer ───────────────────────────────────────────────
# Creates a CLI wrapper and optionally links as an OpenClaw workspace skill.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="${SCRIPT_DIR}/scripts/openrouter_usage.py"
BIN_DIR="${HOME}/.local/bin"
BIN_NAME="openrouter-usage"
SKILL_DIR="${HOME}/.openclaw/workspace/skills"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "╔══════════════════════════════════════╗"
echo "║  openrouter-usage installer          ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}Error: python3 is required but not found.${NC}"
    exit 1
fi

# Ensure script is executable
chmod +x "${SCRIPT_PATH}"

# ── 1. Create CLI wrapper ────────────────────────────────────────────────────

mkdir -p "${BIN_DIR}"

cat > "${BIN_DIR}/${BIN_NAME}" << WRAPPER
#!/bin/bash
exec python3 "${SCRIPT_PATH}" "\$@"
WRAPPER
chmod +x "${BIN_DIR}/${BIN_NAME}"

echo -e "${GREEN}✓${NC} CLI installed: ${BIN_DIR}/${BIN_NAME}"

# Check PATH
if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
    echo ""
    echo -e "${YELLOW}⚠ ${BIN_DIR} is not in your PATH.${NC}"
    echo "  Add this to your shell profile (~/.zshrc, ~/.bashrc, etc.):"
    echo ""
    echo "    export PATH=\"\${HOME}/.local/bin:\${PATH}\""
    echo ""
fi

# ── 2. Link as OpenClaw skill (optional) ─────────────────────────────────────

if [ -d "${HOME}/.openclaw" ]; then
    echo ""
    read -r -p "Link as OpenClaw workspace skill? [Y/n] " response
    response="${response:-Y}"
    if [[ "${response}" =~ ^[Yy]$ ]]; then
        mkdir -p "${SKILL_DIR}"
        LINK_TARGET="${SKILL_DIR}/${BIN_NAME}"

        if [ -L "${LINK_TARGET}" ] || [ -d "${LINK_TARGET}" ]; then
            rm -rf "${LINK_TARGET}"
        fi

        ln -s "${SCRIPT_DIR}" "${LINK_TARGET}"
        echo -e "${GREEN}✓${NC} Skill linked: ${LINK_TARGET} → ${SCRIPT_DIR}"

        # Suggest disabling model-usage if it exists
        if grep -q '"model-usage"' "${HOME}/.openclaw/openclaw.json" 2>/dev/null; then
            echo ""
            echo -e "${YELLOW}Tip:${NC} If you use OpenRouter (not Codex/Claude Code), consider disabling"
            echo "  the bundled model-usage skill to avoid conflicts:"
            echo ""
            echo '    "skills": { "entries": { "model-usage": { "enabled": false } } }'
        fi

        echo ""
        echo "  Restart the daemon to pick up the new skill:"
        echo "    openclaw daemon restart"
    fi
fi

# ── 3. Verify ────────────────────────────────────────────────────────────────

echo ""
if command -v "${BIN_NAME}" &>/dev/null; then
    echo -e "${GREEN}✓${NC} Ready! Try: ${BIN_NAME} report"
else
    echo -e "${GREEN}✓${NC} Installed. After updating PATH, try: ${BIN_NAME} report"
fi
