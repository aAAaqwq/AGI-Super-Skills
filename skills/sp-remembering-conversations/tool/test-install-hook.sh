#!/bin/bash
# Test suite for install-hook script

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_HOOK="$SCRIPT_DIR/install-hook"

# Test counter
TESTS_RUN=0
TESTS_PASSED=0

# Helper functions
setup_test() {
  TEST_DIR=$(mktemp -d)
  export HOME="$TEST_DIR"
  mkdir -p "$HOME/.claude/hooks"
}

cleanup_test() {
  if [ -n "$TEST_DIR" ] && [ -d "$TEST_DIR" ]; then
    rm -rf "$TEST_DIR"
  fi
}

assert_file_exists() {
  if [ ! -f "$1" ]; then
    echo "❌ FAIL: File does not exist: $1"
    return 1
  fi
  return 0
}

assert_file_not_exists() {
  if [ -f "$1" ]; then
    echo "❌ FAIL: File should not exist: $1"
    return 1
  fi
  return 0
}

assert_file_executable() {
  if [ ! -x "$1" ]; then
    echo "❌ FAIL: File is not executable: $1"
    return 1
  fi
  return 0
}

assert_file_contains() {
  if ! grep -q "$2" "$1"; then
    echo "❌ FAIL: File $1 does not contain: $2"
    return 1
  fi
  return 0
}

run_test() {
  local test_name="$1"
  local test_func="$2"

  TESTS_RUN=$((TESTS_RUN + 1))
  echo "Running test: $test_name"

  setup_test

  if $test_func; then
    echo "✓ PASS: $test_name"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "❌ FAIL: $test_name"
  fi

  cleanup_test
  echo ""
}

# Test 1: Fresh installation with no existing hook
test_fresh_installation() {
  # Run installer with no input (non-interactive fresh install)
  if [ ! -x "$INSTALL_HOOK" ]; then
    echo "❌ install-hook script not found or not executable"
    return 1
  fi

  # Should fail because script doesn't exist yet
  "$INSTALL_HOOK" 2>&1 || true

  # Verify hook was created
  assert_file_exists "$HOME/.claude/hooks/sessionEnd" || return 1

  # Verify hook is executable
  assert_file_executable "$HOME/.claude/hooks/sessionEnd" || return 1

  # Verify hook contains indexer reference
  assert_file_contains "$HOME/.claude/hooks/sessionEnd" "remembering-conversations.*index-conversations" || return 1

  return 0
}

# Test 2: Merge with existing hook (user chooses merge)
test_merge_with_existing_hook() {
  # Create existing hook
  cat > "$HOME/.claude/hooks/sessionEnd" <<'EOF'
#!/bin/bash
# Existing hook content
echo "Existing hook running"
EOF
  chmod +x "$HOME/.claude/hooks/sessionEnd"

  # Run installer and choose merge
  echo "m" | "$INSTALL_HOOK" 2>&1 || true

  # Verify backup was created
  local backup_count=$(ls -1 "$HOME/.claude/hooks/sessionEnd.backup."* 2>/dev/null | wc -l)
  if [ "$backup_count" -lt 1 ]; then
    echo "❌ No backup created"
    return 1
  fi

  # Verify original content is preserved
  assert_file_contains "$HOME/.claude/hooks/sessionEnd" "Existing hook running" || return 1

  # Verify indexer was appended
  assert_file_contains "$HOME/.claude/hooks/sessionEnd" "remembering-conversations.*index-conversations" || return 1

  return 0
}

# Test 3: Replace with existing hook (user chooses replace)
test_replace_with_existing_hook() {
  # Create existing hook
  cat > "$HOME/.claude/hooks/sessionEnd" <<'EOF'
#!/bin/bash
# Old hook to be replaced
echo "Old hook"
EOF
  chmod +x "$HOME/.claude/hooks/sessionEnd"

  # Run installer and choose replace
  echo "r" | "$INSTALL_HOOK" 2>&1 || true

  # Verify backup was created
  local backup_count=$(ls -1 "$HOME/.claude/hooks/sessionEnd.backup."* 2>/dev/null | wc -l)
  if [ "$backup_count" -lt 1 ]; then
    echo "❌ No backup created"
    return 1
  fi

  # Verify old content is gone
  if grep -q "Old hook" "$HOME/.claude/hooks/sessionEnd"; then
    echo "❌ Old hook content still present"
    return 1
  fi

  # Verify new hook contains indexer
  assert_file_contains "$HOME/.claude/hooks/sessionEnd" "remembering-conversations.*index-conversations" || return 1

  return 0
}

# Test 4: Detection of already-installed indexer (idempotent)
test_already_installed_detection() {
  # Create hook with indexer already installed
  cat > "$HOME/.claude/hooks/sessionEnd" <<'EOF'
#!/bin/bash
# Auto-index conversations (remembering-conversations skill)
INDEXER="$HOME/.claude/skills/collaboration/remembering-conversations/tool/index-conversations"
if [ -n "$SESSION_ID" ] && [ -x "$INDEXER" ]; then
  "$INDEXER" --session "$SESSION_ID" > /dev/null 2>&1 &
fi
EOF
  chmod +x "$HOME/.claude/hooks/sessionEnd"

  # Run installer - should detect and exit
  local output=$("$INSTALL_HOOK" 2>&1 || true)

  # Verify it detected existing installation
  if ! echo "$output" | grep -q "already installed"; then
    echo "❌ Did not detect existing installation"
    echo "Output: $output"
    return 1
  fi

  # Verify no backup was created (since nothing changed)
  local backup_count=$(ls -1 "$HOME/.claude/hooks/sessionEnd.backup."* 2>/dev/null | wc -l)
  if [ "$backup_count" -gt 0 ]; then
    echo "❌ Backup created when it shouldn't have been"
    return 1
  fi

  return 0
}

# Test 5: Executable permissions are set
test_executable_permissions() {
  # Run installer
  "$INSTALL_HOOK" 2>&1 || true

  # Verify hook is executable
  assert_file_executable "$HOME/.claude/hooks/sessionEnd" || return 1

  return 0
}

# Run all tests
echo "=========================================="
echo "Testing install-hook script"
echo "=========================================="
echo ""

run_test "Fresh installation with no existing hook" test_fresh_installation
run_test "Merge with existing hook" test_merge_with_existing_hook
run_test "Replace with existing hook" test_replace_with_existing_hook
run_test "Detection of already-installed indexer" test_already_installed_detection
run_test "Executable permissions are set" test_executable_permissions

echo "=========================================="
echo "Test Results: $TESTS_PASSED/$TESTS_RUN passed"
echo "=========================================="

if [ $TESTS_PASSED -eq $TESTS_RUN ]; then
  exit 0
else
  exit 1
fi
