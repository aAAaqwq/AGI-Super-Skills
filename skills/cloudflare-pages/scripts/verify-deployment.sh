#!/usr/bin/env bash
# verify-deployment.sh — Check deployment status, list history, verify SSL
#
# Usage: bash verify-deployment.sh <project_name> [custom_domain]
#
# Environment:
#   CLOUDFLARE_ACCOUNT_ID  — Required. Your Cloudflare account ID.
#   CLOUDFLARE_API_TOKEN   — Required. API token with Pages:Read scope.
#
# Requires: jq, curl
#
# Example:
#   export CLOUDFLARE_ACCOUNT_ID="abc123"
#   export CLOUDFLARE_API_TOKEN="your-token"
#   bash verify-deployment.sh my-site myapp.example.com

set -euo pipefail

# --- Colors ---
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# --- Args ---
if [[ $# -lt 1 ]]; then
  echo -e "${RED}Usage: $0 <project_name> [custom_domain]${NC}"
  echo ""
  echo "  project_name   — Cloudflare Pages project name"
  echo "  custom_domain  — Optional. Custom domain to verify SSL for."
  exit 1
fi

PROJECT_NAME="$1"
CUSTOM_DOMAIN="${2:-}"

# --- Validate environment ---
for var in CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_API_TOKEN; do
  if [[ -z "${!var:-}" ]]; then
    echo -e "${RED}Error: ${var} is not set${NC}"
    exit 1
  fi
done

# --- Check dependencies ---
for cmd in jq curl; do
  if ! command -v "$cmd" &>/dev/null; then
    echo -e "${RED}Error: ${cmd} is required but not installed${NC}"
    exit 1
  fi
done

API_BASE="https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/pages/projects/${PROJECT_NAME}"
AUTH_HEADER="Authorization: Bearer ${CLOUDFLARE_API_TOKEN}"

# --- Latest deployment ---
echo -e "${BOLD}Deployment Status: ${PROJECT_NAME}${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

DEPLOYMENTS=$(curl -s -X GET "${API_BASE}/deployments?per_page=5" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json")

DEPLOY_SUCCESS=$(echo "$DEPLOYMENTS" | jq -r '.success')
if [[ "$DEPLOY_SUCCESS" != "true" ]]; then
  echo -e "${RED}Failed to fetch deployments${NC}"
  echo "$DEPLOYMENTS" | jq '.errors'
  exit 1
fi

DEPLOY_COUNT=$(echo "$DEPLOYMENTS" | jq -r '.result | length')
if [[ "$DEPLOY_COUNT" -eq 0 ]]; then
  echo -e "${YELLOW}No deployments found${NC}"
  exit 0
fi

# Latest deployment details
LATEST=$(echo "$DEPLOYMENTS" | jq -r '.result[0]')
LATEST_ID=$(echo "$LATEST" | jq -r '.id' | cut -c1-8)
LATEST_STATUS=$(echo "$LATEST" | jq -r '.latest_stage.status')
LATEST_URL=$(echo "$LATEST" | jq -r '.url')
LATEST_ENV=$(echo "$LATEST" | jq -r '.environment')
LATEST_CREATED=$(echo "$LATEST" | jq -r '.created_on')

# Color-code status
case "$LATEST_STATUS" in
  success) STATUS_COLOR="${GREEN}" ;;
  failure) STATUS_COLOR="${RED}" ;;
  *)       STATUS_COLOR="${YELLOW}" ;;
esac

echo ""
echo -e "  Latest:  ${STATUS_COLOR}${BOLD}${LATEST_STATUS}${NC}"
echo -e "  ID:      ${DIM}${LATEST_ID}...${NC}"
echo -e "  Env:     ${LATEST_ENV}"
echo -e "  URL:     ${CYAN}${LATEST_URL}${NC}"
echo -e "  Created: ${LATEST_CREATED}"

# --- Deployment history ---
echo ""
echo -e "${BOLD}Recent Deployments${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "  ${DIM}%-10s %-12s %-12s %s${NC}\n" "ID" "STATUS" "ENV" "CREATED"

echo "$DEPLOYMENTS" | jq -r '.result[] | "\(.id | .[0:8])  \(.latest_stage.status)  \(.environment)  \(.created_on)"' | while read -r line; do
  ID=$(echo "$line" | awk '{print $1}')
  STATUS=$(echo "$line" | awk '{print $2}')
  ENV=$(echo "$line" | awk '{print $3}')
  CREATED=$(echo "$line" | awk '{print $4}')

  case "$STATUS" in
    success) SC="${GREEN}" ;;
    failure) SC="${RED}" ;;
    *)       SC="${YELLOW}" ;;
  esac

  printf "  %-10s ${SC}%-12s${NC} %-12s %s\n" "$ID..." "$STATUS" "$ENV" "$CREATED"
done

# --- Custom domain check ---
if [[ -n "$CUSTOM_DOMAIN" ]]; then
  echo ""
  echo -e "${BOLD}Custom Domain: ${CUSTOM_DOMAIN}${NC}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  # Check domain registration on Pages
  DOMAINS=$(curl -s -X GET "${API_BASE}/domains" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json")

  DOMAIN_MATCH=$(echo "$DOMAINS" | jq -r ".result[] | select(.name == \"${CUSTOM_DOMAIN}\")")

  if [[ -n "$DOMAIN_MATCH" ]]; then
    DOMAIN_STATUS=$(echo "$DOMAIN_MATCH" | jq -r '.status')
    case "$DOMAIN_STATUS" in
      active)  DS_COLOR="${GREEN}" ;;
      pending) DS_COLOR="${YELLOW}" ;;
      *)       DS_COLOR="${RED}" ;;
    esac
    echo -e "  Registration: ${DS_COLOR}${DOMAIN_STATUS}${NC}"
  else
    echo -e "  Registration: ${RED}not found${NC}"
  fi

  # Check SSL via HTTPS
  echo -n "  SSL check:    "
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://${CUSTOM_DOMAIN}" 2>/dev/null || echo "000")
  if [[ "$HTTP_CODE" =~ ^(200|301|302|304)$ ]]; then
    echo -e "${GREEN}OK (HTTP ${HTTP_CODE})${NC}"
  elif [[ "$HTTP_CODE" == "000" ]]; then
    echo -e "${RED}unreachable${NC}"
  else
    echo -e "${YELLOW}HTTP ${HTTP_CODE}${NC}"
  fi
fi

# --- Pages.dev check ---
echo ""
echo -e "${BOLD}Pages.dev Check${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
PAGES_URL="https://${PROJECT_NAME}.pages.dev"
echo -n "  ${PAGES_URL}: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$PAGES_URL" 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "200" ]]; then
  echo -e "${GREEN}OK${NC}"
elif [[ "$HTTP_CODE" == "000" ]]; then
  echo -e "${RED}unreachable${NC}"
else
  echo -e "${YELLOW}HTTP ${HTTP_CODE}${NC}"
fi
