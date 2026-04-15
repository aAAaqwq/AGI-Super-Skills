#!/usr/bin/env bash
# setup-pages-project.sh — Create a Cloudflare Pages project via wrangler
#
# Usage: bash setup-pages-project.sh <project_name> <build_command> <output_dir> [branch]
#
# Environment:
#   CLOUDFLARE_ACCOUNT_ID  — Required. Your Cloudflare account ID.
#
# Example:
#   export CLOUDFLARE_ACCOUNT_ID="abc123"
#   bash setup-pages-project.sh my-site "npm run build" dist main

set -euo pipefail

# --- Colors ---
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# --- Args ---
if [[ $# -lt 3 ]]; then
  echo -e "${RED}Usage: $0 <project_name> <build_command> <output_dir> [branch]${NC}"
  echo ""
  echo "  project_name   — Name for the Pages project (becomes <name>.pages.dev)"
  echo "  build_command   — Build command (e.g. \"hugo --minify\", \"npm run build\")"
  echo "  output_dir      — Build output directory (e.g. dist, public, out)"
  echo "  branch          — Production branch (default: main)"
  exit 1
fi

PROJECT_NAME="$1"
BUILD_COMMAND="$2"
OUTPUT_DIR="$3"
BRANCH="${4:-main}"

# --- Validate environment ---
if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo -e "${RED}Error: CLOUDFLARE_ACCOUNT_ID is not set${NC}"
  echo "  export CLOUDFLARE_ACCOUNT_ID=\"<your-account-id>\""
  exit 1
fi

# --- Check wrangler ---
if ! command -v wrangler &>/dev/null; then
  echo -e "${RED}Error: wrangler CLI not found${NC}"
  echo "  Install: npm i -g wrangler"
  echo "  Then:    wrangler login"
  exit 1
fi

# --- Verify authentication ---
echo -e "${CYAN}Checking wrangler authentication...${NC}"
if ! wrangler whoami &>/dev/null; then
  echo -e "${RED}Error: wrangler is not authenticated${NC}"
  echo "  Run: wrangler login"
  exit 1
fi

# --- Create project ---
echo -e "${CYAN}Creating Pages project: ${BOLD}${PROJECT_NAME}${NC}"
echo "  Production branch: ${BRANCH}"
echo "  Build command:     ${BUILD_COMMAND}"
echo "  Output directory:  ${OUTPUT_DIR}"
echo ""

wrangler pages project create "$PROJECT_NAME" --production-branch "$BRANCH"

echo ""
echo -e "${GREEN}${BOLD}Project created successfully!${NC}"
echo ""
echo -e "  Pages URL:  ${CYAN}https://${PROJECT_NAME}.pages.dev${NC}"
echo ""
echo "Next steps:"
echo "  1. Build your site:  ${BUILD_COMMAND}"
echo "  2. Deploy:           wrangler pages deploy ${OUTPUT_DIR} --project-name ${PROJECT_NAME}"
