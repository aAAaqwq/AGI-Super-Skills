#!/usr/bin/env bash
# god setup - First-run setup for god-mode
# Creates directories, initializes database, checks dependencies

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/lib"

# Source libraries
source "$LIB_DIR/output.sh"
source "$LIB_DIR/config.sh"
source "$LIB_DIR/db.sh"

header "god-mode Setup"

# Track setup status
ERRORS=0

# Step 1: Check dependencies
echo -e "${BOLD}Checking dependencies...${RESET}"
echo ""

# Check gh CLI
echo -n "  gh (GitHub CLI): "
if command -v gh &>/dev/null; then
    GH_VERSION=$(gh --version | head -1)
    success "installed ($GH_VERSION)"

    # Check if authenticated
    echo -n "  gh authentication: "
    if gh auth status &>/dev/null; then
        GH_USER=$(gh api user --jq '.login' 2>/dev/null || echo "unknown")
        success "logged in as $GH_USER"
    else
        warn "not authenticated"
        echo "    Run: gh auth login"
        ((ERRORS++)) || true
    fi
else
    error "not installed"
    echo "    Install: https://cli.github.com/"
    ((ERRORS++)) || true
fi

# Check sqlite3
echo -n "  sqlite3: "
if command -v sqlite3 &>/dev/null; then
    SQLITE_VERSION=$(sqlite3 --version | cut -d' ' -f1)
    success "installed ($SQLITE_VERSION)"
else
    error "not installed"
    echo "    Install: apt install sqlite3 (Debian) / brew install sqlite (macOS)"
    ((ERRORS++)) || true
fi

# Check jq
echo -n "  jq: "
if command -v jq &>/dev/null; then
    JQ_VERSION=$(jq --version)
    success "installed ($JQ_VERSION)"
else
    error "not installed"
    echo "    Install: apt install jq (Debian) / brew install jq (macOS)"
    ((ERRORS++)) || true
fi

# Check yq (optional but recommended)
echo -n "  yq (optional): "
if command -v yq &>/dev/null; then
    YQ_VERSION=$(yq --version 2>/dev/null | head -1)
    success "installed ($YQ_VERSION)"
else
    warn "not installed (using fallback parser)"
    echo "    Recommended: brew install yq / snap install yq"
fi

echo ""

# Step 2: Create directories
echo -e "${BOLD}Setting up directories...${RESET}"
echo ""

# Data directory
echo -n "  Data directory (~/.god-mode): "
if [[ -d "$HOME/.god-mode" ]]; then
    success "exists"
else
    mkdir -p "$HOME/.god-mode"
    success "created"
fi

# Config directory
echo -n "  Config directory (~/.config/god-mode): "
CONFIG_DIR="$HOME/.config/god-mode"
if [[ -d "$CONFIG_DIR" ]]; then
    success "exists"
else
    mkdir -p "$CONFIG_DIR"
    success "created"
fi

echo ""

# Step 3: Initialize database
echo -e "${BOLD}Initializing database...${RESET}"
echo ""

echo -n "  SQLite database: "
db_init
success "ready"

echo ""

# Step 4: Create config if needed
echo -e "${BOLD}Configuration...${RESET}"
echo ""

echo -n "  Config file: "
if [[ -f "$GOD_MODE_CONFIG" ]]; then
    success "exists"
else
    config_init
    success "created default"
fi

echo ""

# Step 5: Summary
divider
echo ""

if [[ $ERRORS -gt 0 ]]; then
    warn "Setup completed with $ERRORS issue(s)"
    echo ""
    echo "Please resolve the issues above, then run 'god setup' again."
else
    success "Setup complete!"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. Add a project:"
    echo "     ${BOLD}god projects add github:yourusername/yourrepo${RESET}"
    echo ""
    echo "  2. Sync data:"
    echo "     ${BOLD}god sync${RESET}"
    echo ""
    echo "  3. View status:"
    echo "     ${BOLD}god status${RESET}"
    echo ""
    echo "  4. Analyze your agents.md:"
    echo "     ${BOLD}god agents analyze yourrepo${RESET}"
fi

# Interactive: offer to add first project
if [[ $ERRORS -eq 0 ]]; then
    echo ""
    divider
    echo ""

    PROJECT_COUNT=$(config_project_count)
    if [[ "$PROJECT_COUNT" -eq 0 ]]; then
        echo "Would you like to add your first project now?"
        echo -n "Enter a GitHub repo (e.g., user/repo) or press Enter to skip: "
        read -r FIRST_REPO

        if [[ -n "$FIRST_REPO" ]]; then
            # Normalize input
            FIRST_REPO="${FIRST_REPO#github:}"
            FIRST_REPO="${FIRST_REPO#https://github.com/}"

            echo ""
            echo -n "Adding github:$FIRST_REPO... "

            # Check if repo exists
            if gh repo view "$FIRST_REPO" &>/dev/null; then
                config_add_project "github:$FIRST_REPO" "" "medium" >/dev/null
                db_upsert_project "github:$FIRST_REPO" "github" "$FIRST_REPO" "medium" "[]" ""
                success "added"

                echo ""
                echo "Syncing data (this may take a moment)..."
                "$SCRIPT_DIR/commands/sync.sh" "github:$FIRST_REPO"
            else
                error "Repository not found or not accessible"
                echo "Make sure you have access to this repository."
            fi
        fi
    fi
fi

echo ""
