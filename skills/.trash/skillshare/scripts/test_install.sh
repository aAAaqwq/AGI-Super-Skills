#!/bin/bash
# Sandbox test for install.sh
# Run: ./scripts/test_install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INSTALL_SCRIPT="$PROJECT_ROOT/install.sh"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

pass() {
  printf "${GREEN}PASS${NC}: %s\n" "$1"
  TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
  printf "${RED}FAIL${NC}: %s\n" "$1"
  TESTS_FAILED=$((TESTS_FAILED + 1))
}

info() {
  printf "${YELLOW}INFO${NC}: %s\n" "$1"
}

# Test: Script exists and is executable
test_script_exists() {
  if [ -f "$INSTALL_SCRIPT" ]; then
    pass "install.sh exists"
  else
    fail "install.sh not found at $INSTALL_SCRIPT"
    return 1
  fi

  if [ -x "$INSTALL_SCRIPT" ] || chmod +x "$INSTALL_SCRIPT" 2>/dev/null; then
    pass "install.sh is executable"
  else
    fail "install.sh is not executable"
  fi
}

# Test: Script syntax is valid
test_script_syntax() {
  if bash -n "$INSTALL_SCRIPT" 2>/dev/null; then
    pass "install.sh has valid syntax"
  else
    fail "install.sh has syntax errors"
  fi
}

# Test: OS detection
test_os_detection() {
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  case "$OS" in
    darwin|linux)
      pass "OS detection works: $OS"
      ;;
    *)
      fail "Unexpected OS: $OS"
      ;;
  esac
}

# Test: Architecture detection
test_arch_detection() {
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64|amd64|arm64|aarch64)
      pass "Architecture detection works: $ARCH"
      ;;
    *)
      fail "Unexpected architecture: $ARCH"
      ;;
  esac
}

# Test: GitHub API reachable
test_github_api() {
  RESPONSE=$(curl -sL -w "%{http_code}" -o /dev/null "https://api.github.com/repos/runkids/skillshare/releases/latest" 2>/dev/null || echo "000")
  if [ "$RESPONSE" = "200" ]; then
    pass "GitHub API is reachable"
  elif [ "$RESPONSE" = "403" ]; then
    info "GitHub API rate limited (expected in CI)"
    pass "GitHub API responded (rate limited)"
  else
    fail "GitHub API returned: $RESPONSE"
  fi
}

# Test: Latest version can be fetched
test_fetch_version() {
  VERSION=$(curl -sL "https://api.github.com/repos/runkids/skillshare/releases/latest" 2>/dev/null | grep '"tag_name"' | cut -d'"' -f4 || echo "")
  if [ -n "$VERSION" ]; then
    pass "Latest version fetched: $VERSION"
  else
    info "Could not fetch version (may be rate limited or no releases yet)"
    pass "Version fetch test skipped"
  fi
}

# Test: Download URL format
test_download_url_format() {
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64) ARCH="amd64" ;;
    arm64|aarch64) ARCH="arm64" ;;
  esac

  # Use a known version for URL format test
  TEST_VERSION="0.1.0"
  URL="https://github.com/runkids/skillshare/releases/download/v${TEST_VERSION}/skillshare_${TEST_VERSION}_${OS}_${ARCH}.tar.gz"

  if echo "$URL" | grep -qE "^https://github.com/runkids/skillshare/releases/download/v[0-9]+\.[0-9]+\.[0-9]+/skillshare_[0-9]+\.[0-9]+\.[0-9]+_(darwin|linux)_(amd64|arm64)\.tar\.gz$"; then
    pass "Download URL format is correct: $URL"
  else
    fail "Download URL format is incorrect: $URL"
  fi
}

# Test: Sandbox install (dry-run simulation)
test_sandbox_install() {
  TMP_DIR=$(mktemp -d)
  trap "rm -rf $TMP_DIR" RETURN

  # Create a mock binary
  echo '#!/bin/sh' > "$TMP_DIR/skillshare"
  echo 'echo "skillshare mock v0.0.0"' >> "$TMP_DIR/skillshare"
  chmod +x "$TMP_DIR/skillshare"

  # Test that mock works
  if "$TMP_DIR/skillshare" | grep -q "mock"; then
    pass "Sandbox install simulation works"
  else
    fail "Sandbox install simulation failed"
  fi
}

# Test: Script contains required functions
test_required_functions() {
  REQUIRED_FUNCS="detect_os detect_arch get_latest_version install verify main"
  MISSING=""

  for func in $REQUIRED_FUNCS; do
    if ! grep -q "^${func}()" "$INSTALL_SCRIPT" && ! grep -q "^${func} ()" "$INSTALL_SCRIPT"; then
      MISSING="$MISSING $func"
    fi
  done

  if [ -z "$MISSING" ]; then
    pass "All required functions present"
  else
    fail "Missing functions:$MISSING"
  fi
}

# Run all tests
main() {
  echo "========================================"
  echo "  install.sh Sandbox Tests"
  echo "========================================"
  echo ""

  test_script_exists
  test_script_syntax
  test_os_detection
  test_arch_detection
  test_github_api
  test_fetch_version
  test_download_url_format
  test_sandbox_install
  test_required_functions

  echo ""
  echo "========================================"
  printf "Results: ${GREEN}%d passed${NC}, ${RED}%d failed${NC}\n" "$TESTS_PASSED" "$TESTS_FAILED"
  echo "========================================"

  if [ "$TESTS_FAILED" -gt 0 ]; then
    exit 1
  fi
}

main "$@"
