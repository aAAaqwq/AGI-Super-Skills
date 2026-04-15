#!/usr/bin/env bash
# add-custom-domain.sh — Register a custom domain on a Cloudflare Pages project + create CNAME
#
# Usage: bash add-custom-domain.sh <custom_domain> <project_name>
#
# Environment:
#   CLOUDFLARE_ACCOUNT_ID   — Required. Your Cloudflare account ID.
#   CLOUDFLARE_API_TOKEN    — Required. API token with Pages:Edit scope.
#   CLOUDFLARE_ZONE_ID      — Required. Zone ID for the domain's DNS zone.
#   CLOUDFLARE_DNS_TOKEN    — Optional. Separate token with DNS:Edit scope.
#                              Falls back to CLOUDFLARE_API_TOKEN if not set.
#
# Requires: jq, curl
#
# Example:
#   export CLOUDFLARE_ACCOUNT_ID="abc123"
#   export CLOUDFLARE_API_TOKEN="pages-token"
#   export CLOUDFLARE_ZONE_ID="zone456"
#   export CLOUDFLARE_DNS_TOKEN="dns-token"   # optional
#   bash add-custom-domain.sh myapp.example.com my-pages-project

set -euo pipefail

# --- Colors ---
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# --- Args ---
if [[ $# -lt 2 ]]; then
  echo -e "${RED}Usage: $0 <custom_domain> <project_name>${NC}"
  echo ""
  echo "  custom_domain  — e.g. myapp.example.com"
  echo "  project_name   — Cloudflare Pages project name"
  exit 1
fi

CUSTOM_DOMAIN="$1"
PROJECT_NAME="$2"

# --- Validate environment ---
for var in CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_API_TOKEN CLOUDFLARE_ZONE_ID; do
  if [[ -z "${!var:-}" ]]; then
    echo -e "${RED}Error: ${var} is not set${NC}"
    exit 1
  fi
done

# DNS token falls back to API token
DNS_TOKEN="${CLOUDFLARE_DNS_TOKEN:-$CLOUDFLARE_API_TOKEN}"

# --- Check dependencies ---
for cmd in jq curl; do
  if ! command -v "$cmd" &>/dev/null; then
    echo -e "${RED}Error: ${cmd} is required but not installed${NC}"
    exit 1
  fi
done

# --- Step 1: Register domain on Pages project ---
echo -e "${CYAN}Step 1: Registering ${BOLD}${CUSTOM_DOMAIN}${NC}${CYAN} on project ${BOLD}${PROJECT_NAME}${NC}"

PAGES_API="https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/pages/projects/${PROJECT_NAME}/domains"

RESPONSE=$(curl -s -X POST "$PAGES_API" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"${CUSTOM_DOMAIN}\"}")

SUCCESS=$(echo "$RESPONSE" | jq -r '.success')
ERRORS=$(echo "$RESPONSE" | jq -r '.errors[]?.message // empty')

if [[ "$SUCCESS" == "true" ]]; then
  echo -e "${GREEN}  Domain registered on Pages project${NC}"
elif echo "$ERRORS" | grep -qi "already"; then
  echo -e "${YELLOW}  Domain already registered (skipping)${NC}"
else
  echo -e "${RED}  Failed to register domain${NC}"
  echo "$RESPONSE" | jq .
  exit 1
fi

# --- Step 2: Create CNAME DNS record ---
echo -e "${CYAN}Step 2: Creating CNAME record${NC}"
echo "  ${CUSTOM_DOMAIN} → ${PROJECT_NAME}.pages.dev (proxied)"

DNS_API="https://api.cloudflare.com/client/v4/zones/${CLOUDFLARE_ZONE_ID}/dns_records"

# Extract subdomain (part before the zone's domain)
# For "app.example.com" on zone "example.com", the CNAME name is "app.example.com"
CNAME_NAME="$CUSTOM_DOMAIN"
CNAME_TARGET="${PROJECT_NAME}.pages.dev"

# Check for existing CNAME
EXISTING=$(curl -s -X GET "${DNS_API}?type=CNAME&name=${CNAME_NAME}" \
  -H "Authorization: Bearer ${DNS_TOKEN}" \
  -H "Content-Type: application/json")

EXISTING_COUNT=$(echo "$EXISTING" | jq -r '.result | length')

if [[ "$EXISTING_COUNT" -gt 0 ]]; then
  EXISTING_TARGET=$(echo "$EXISTING" | jq -r '.result[0].content')
  if [[ "$EXISTING_TARGET" == "$CNAME_TARGET" ]]; then
    echo -e "${YELLOW}  CNAME already exists and points to ${CNAME_TARGET} (skipping)${NC}"
  else
    echo -e "${RED}  CNAME exists but points to ${EXISTING_TARGET} (not ${CNAME_TARGET})${NC}"
    echo "  Delete the existing record manually and re-run this script."
    exit 1
  fi
else
  # Create the CNAME record
  DNS_RESPONSE=$(curl -s -X POST "$DNS_API" \
    -H "Authorization: Bearer ${DNS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"type\":\"CNAME\",\"name\":\"${CNAME_NAME}\",\"content\":\"${CNAME_TARGET}\",\"proxied\":true,\"ttl\":1}")

  DNS_SUCCESS=$(echo "$DNS_RESPONSE" | jq -r '.success')

  if [[ "$DNS_SUCCESS" == "true" ]]; then
    echo -e "${GREEN}  CNAME record created${NC}"
  else
    echo -e "${RED}  Failed to create CNAME record${NC}"
    echo "$DNS_RESPONSE" | jq .
    exit 1
  fi
fi

# --- Done ---
echo ""
echo -e "${GREEN}${BOLD}Custom domain setup complete!${NC}"
echo ""
echo "  Domain:    https://${CUSTOM_DOMAIN}"
echo "  Pages URL: https://${PROJECT_NAME}.pages.dev"
echo ""
echo "SSL will be provisioned automatically (typically 30-60 seconds)."
echo "Run verify-deployment.sh to check status."
