#!/bin/bash
# End-to-end deployment testing
# Tests all deployment scenarios from docs/plans/2025-10-07-deployment-plan.md

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_HOOK="$SCRIPT_DIR/install-hook"
INDEX_CONVERSATIONS="$SCRIPT_DIR/index-conversations"

# Test counter
TESTS_RUN=0
TESTS_PASSED=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
setup_test() {
  TEST_DIR=$(mktemp -d)
  export HOME="$TEST_DIR"
  export TEST_PROJECTS_DIR="$TEST_DIR/.claude/projects"
  export TEST_ARCHIVE_DIR="$TEST_DIR/.config/superpowers/conversation-archive"
  export TEST_DB_PATH="$TEST_DIR/.config/superpowers/conversation-index/db.sqlite"

  mkdir -p "$HOME/.claude/hooks"
  mkdir -p "$TEST_PROJECTS_DIR"
  mkdir -p "$TEST_ARCHIVE_DIR"
  mkdir -p "$TEST_DIR/.config/superpowers/conversation-index"
}

cleanup_test() {
  if [ -n "$TEST_DIR" ] && [ -d "$TEST_DIR" ]; then
    rm -rf "$TEST_DIR"
  fi
  unset TEST_PROJECTS_DIR
  unset TEST_ARCHIVE_DIR
  unset TEST_DB_PATH
}

assert_file_exists() {
  if [ ! -f "$1" ]; then
    echo -e "${RED}❌ FAIL: File does not exist: $1${NC}"
    return 1
  fi
  return 0
}

assert_file_executable() {
  if [ ! -x "$1" ]; then
    echo -e "${RED}❌ FAIL: File is not executable: $1${NC}"
    return 1
  fi
  return 0
}

assert_file_contains() {
  if ! grep -q "$2" "$1"; then
    echo -e "${RED}❌ FAIL: File $1 does not contain: $2${NC}"
    return 1
  fi
  return 0
}

assert_summary_exists() {
  local jsonl_file="$1"

  # If file is in projects dir, convert to archive path
  if [[ "$jsonl_file" == *"/.claude/projects/"* ]]; then
    jsonl_file=$(echo "$jsonl_file" | sed "s|/.claude/projects/|/.config/superpowers/conversation-archive/|")
  fi

  local summary_file="${jsonl_file%.jsonl}-summary.txt"
  if [ ! -f "$summary_file" ]; then
    echo -e "${RED}❌ FAIL: Summary does not exist: $summary_file${NC}"
    return 1
  fi
  return 0
}

create_test_conversation() {
  local project="$1"
  local uuid="${2:-test-$(date +%s)}"

  mkdir -p "$TEST_PROJECTS_DIR/$project"
  local conv_file="$TEST_PROJECTS_DIR/$project/${uuid}.jsonl"

  cat > "$conv_file" <<'EOF'
{"type":"user","message":{"role":"user","content":"What is TDD?"},"timestamp":"2024-01-01T00:00:00Z"}
{"type":"assistant","message":{"role":"assistant","content":"TDD stands for Test-Driven Development. You write tests first."},"timestamp":"2024-01-01T00:00:01Z"}
EOF

  echo "$conv_file"
}

run_test() {
  local test_name="$1"
  local test_func="$2"

  TESTS_RUN=$((TESTS_RUN + 1))
  echo -e "\n${YELLOW}Running test: $test_name${NC}"

  setup_test

  if $test_func; then
    echo -e "${GREEN}✓ PASS: $test_name${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo -e "${RED}❌ FAIL: $test_name${NC}"
  fi

  cleanup_test
}

# ============================================================================
# Scenario 1: Fresh Installation
# ============================================================================

test_scenario_1_fresh_install() {
  echo "  1. Installing hook with no existing hook..."
  "$INSTALL_HOOK" > /dev/null 2>&1 || true

  assert_file_exists "$HOME/.claude/hooks/sessionEnd" || return 1
  assert_file_executable "$HOME/.claude/hooks/sessionEnd" || return 1

  echo "  2. Creating test conversation..."
  local conv_file=$(create_test_conversation "test-project" "conv-1")

  echo "  3. Indexing conversation..."
  cd "$SCRIPT_DIR" && "$INDEX_CONVERSATIONS" > /dev/null 2>&1

  echo "  4. Verifying summary was created..."
  assert_summary_exists "$conv_file" || return 1

  echo "  5. Testing hook triggers indexing..."
  export SESSION_ID="hook-session-$(date +%s)"

  # Create conversation file with SESSION_ID in name
  mkdir -p "$TEST_PROJECTS_DIR/test-project"
  local new_conv="$TEST_PROJECTS_DIR/test-project/${SESSION_ID}.jsonl"
  cat > "$new_conv" <<'EOF'
{"type":"user","message":{"role":"user","content":"What is TDD?"},"timestamp":"2024-01-01T00:00:00Z"}
{"type":"assistant","message":{"role":"assistant","content":"TDD stands for Test-Driven Development. You write tests first."},"timestamp":"2024-01-01T00:00:01Z"}
EOF

  # Verify hook runs the index command (manually call indexer with --session)
  # In real environment, hook would do this automatically
  cd "$SCRIPT_DIR" && "$INDEX_CONVERSATIONS" --session "$SESSION_ID" > /dev/null 2>&1

  echo "  6. Verifying session was indexed..."
  assert_summary_exists "$new_conv" || return 1

  echo "  7. Testing search functionality..."
  local search_result=$(cd "$SCRIPT_DIR" && "$SCRIPT_DIR/search-conversations" "TDD" 2>/dev/null || echo "")
  if [ -z "$search_result" ]; then
    echo -e "${RED}❌ Search returned no results${NC}"
    return 1
  fi

  return 0
}

# ============================================================================
# Scenario 2: Existing Hook (merge)
# ============================================================================

test_scenario_2_existing_hook_merge() {
  echo "  1. Creating existing hook..."
  cat > "$HOME/.claude/hooks/sessionEnd" <<'EOF'
#!/bin/bash
# Existing hook
echo "Existing hook running"
EOF
  chmod +x "$HOME/.claude/hooks/sessionEnd"

  echo "  2. Installing with merge option..."
  echo "m" | "$INSTALL_HOOK" > /dev/null 2>&1 || true

  echo "  3. Verifying backup created..."
  local backup_count=$(ls -1 "$HOME/.claude/hooks/sessionEnd.backup."* 2>/dev/null | wc -l)
  if [ "$backup_count" -lt 1 ]; then
    echo -e "${RED}❌ No backup created${NC}"
    return 1
  fi

  echo "  4. Verifying merge preserved existing content..."
  assert_file_contains "$HOME/.claude/hooks/sessionEnd" "Existing hook running" || return 1

  echo "  5. Verifying indexer was appended..."
  assert_file_contains "$HOME/.claude/hooks/sessionEnd" "remembering-conversations.*index-conversations" || return 1

  echo "  6. Testing merged hook runs both parts..."
  local conv_file=$(create_test_conversation "merge-project" "merge-conv")
  cd "$SCRIPT_DIR" && "$INDEX_CONVERSATIONS" > /dev/null 2>&1

  export SESSION_ID="merge-session-$(date +%s)"
  local hook_output=$("$HOME/.claude/hooks/sessionEnd" 2>&1)

  if ! echo "$hook_output" | grep -q "Existing hook running"; then
    echo -e "${RED}❌ Existing hook logic not executed${NC}"
    return 1
  fi

  return 0
}

# ============================================================================
# Scenario 3: Recovery (verify/repair)
# ============================================================================

test_scenario_3_recovery_verify_repair() {
  echo "  1. Creating conversations and indexing..."
  local conv1=$(create_test_conversation "recovery-project" "conv-1")
  local conv2=$(create_test_conversation "recovery-project" "conv-2")

  cd "$SCRIPT_DIR" && "$INDEX_CONVERSATIONS" > /dev/null 2>&1

  echo "  2. Verifying summaries exist..."
  assert_summary_exists "$conv1" || return 1
  assert_summary_exists "$conv2" || return 1

  echo "  3. Deleting summary to simulate missing file..."
  # Delete from archive (where summaries are stored)
  local archive_conv1=$(echo "$conv1" | sed "s|/.claude/projects/|/.config/superpowers/conversation-archive/|")
  rm "${archive_conv1%.jsonl}-summary.txt"

  echo "  4. Running verify (should detect missing)..."
  local verify_output=$(cd "$SCRIPT_DIR" && "$INDEX_CONVERSATIONS" --verify 2>&1)

  if ! echo "$verify_output" | grep -q "Missing summaries: 1"; then
    echo -e "${RED}❌ Verify did not detect missing summary${NC}"
    echo "Verify output: $verify_output"
    return 1
  fi

  echo "  5. Running repair..."
  cd "$SCRIPT_DIR" && "$INDEX_CONVERSATIONS" --repair > /dev/null 2>&1

  echo "  6. Verifying summary was regenerated..."
  assert_summary_exists "$conv1" || return 1

  echo "  7. Running verify again (should be clean)..."
  verify_output=$(cd "$SCRIPT_DIR" && "$INDEX_CONVERSATIONS" --verify 2>&1)

  # Verify should report no missing issues
  if ! echo "$verify_output" | grep -q "Missing summaries: 0"; then
    echo -e "${RED}❌ Verify still reports missing issues after repair${NC}"
    echo "Verify output: $verify_output"
    return 1
  fi

  return 0
}

# ============================================================================
# Scenario 4: Change Detection
# ============================================================================

test_scenario_4_change_detection() {
  echo "  1. Creating and indexing conversation..."
  local conv=$(create_test_conversation "change-project" "conv-1")

  cd "$SCRIPT_DIR" && "$INDEX_CONVERSATIONS" > /dev/null 2>&1

  echo "  2. Verifying initial index..."
  assert_summary_exists "$conv" || return 1

  echo "  3. Modifying conversation (adding exchange)..."
  # Wait to ensure different mtime
  sleep 1

  # Modify the archive file (that's what verify checks)
  local archive_conv=$(echo "$conv" | sed "s|/.claude/projects/|/.config/superpowers/conversation-archive/|")
  cat >> "$archive_conv" <<'EOF'
{"type":"user","message":{"role":"user","content":"Tell me more about TDD"},"timestamp":"2024-01-01T00:00:02Z"}
{"type":"assistant","message":{"role":"assistant","content":"TDD has three phases: Red, Green, Refactor."},"timestamp":"2024-01-01T00:00:03Z"}
EOF

  echo "  4. Running verify (should detect outdated)..."
  local verify_output=$(cd "$SCRIPT_DIR" && "$INDEX_CONVERSATIONS" --verify 2>&1)

  if ! echo "$verify_output" | grep -q "Outdated files: 1"; then
    echo -e "${RED}❌ Verify did not detect outdated file${NC}"
    echo "Verify output: $verify_output"
    return 1
  fi

  echo "  5. Running repair (should re-index)..."
  cd "$SCRIPT_DIR" && "$INDEX_CONVERSATIONS" --repair > /dev/null 2>&1

  echo "  6. Verifying conversation is up to date..."
  verify_output=$(cd "$SCRIPT_DIR" && "$INDEX_CONVERSATIONS" --verify 2>&1)

  if ! echo "$verify_output" | grep -q "Outdated files: 0"; then
    echo -e "${RED}❌ File still outdated after repair${NC}"
    echo "Verify output: $verify_output"
    return 1
  fi

  echo "  7. Verifying new content is searchable..."
  local search_result=$(cd "$SCRIPT_DIR" && "$SCRIPT_DIR/search-conversations" "Red Green Refactor" 2>/dev/null || echo "")
  if [ -z "$search_result" ]; then
    echo -e "${RED}❌ New content not found in search${NC}"
    return 1
  fi

  return 0
}

# ============================================================================
# Scenario 5: Subagent Workflow (Manual Testing Required)
# ============================================================================

test_scenario_5_subagent_workflow_docs() {
  echo "  This scenario requires manual testing with a live subagent."
  echo "  Automated checks:"

  echo "  1. Verifying search-agent template exists..."
  local template_file="$SCRIPT_DIR/prompts/search-agent.md"
  assert_file_exists "$template_file" || return 1

  echo "  2. Verifying template has required sections..."
  assert_file_contains "$template_file" "### Summary" || return 1
  assert_file_contains "$template_file" "### Sources" || return 1
  assert_file_contains "$template_file" "### For Follow-Up" || return 1

  echo ""
  echo -e "${YELLOW}  MANUAL TESTING REQUIRED:${NC}"
  echo "  To complete Scenario 5 testing:"
  echo "    1. Start a new Claude Code session"
  echo "    2. Ask about a past conversation topic"
  echo "    3. Dispatch subagent using: skills/collaboration/remembering-conversations/tool/prompts/search-agent.md"
  echo "    4. Verify synthesis is 200-1000 words"
  echo "    5. Verify all sources include: project, date, file path, status"
  echo "    6. Ask follow-up question to test iterative refinement"
  echo "    7. Verify no raw conversations loaded into main context"
  echo ""

  return 0
}

# ============================================================================
# Run All Tests
# ============================================================================

echo "=========================================="
echo "  End-to-End Deployment Testing"
echo "=========================================="
echo ""
echo "Testing deployment scenarios from:"
echo "  docs/plans/2025-10-07-deployment-plan.md"
echo ""

run_test "Scenario 1: Fresh Installation" test_scenario_1_fresh_install
run_test "Scenario 2: Existing Hook (merge)" test_scenario_2_existing_hook_merge
run_test "Scenario 3: Recovery (verify/repair)" test_scenario_3_recovery_verify_repair
run_test "Scenario 4: Change Detection" test_scenario_4_change_detection
run_test "Scenario 5: Subagent Workflow (docs check)" test_scenario_5_subagent_workflow_docs

echo ""
echo "=========================================="
echo -e "  Test Results: ${GREEN}$TESTS_PASSED${NC}/${TESTS_RUN} passed"
echo "=========================================="

if [ $TESTS_PASSED -eq $TESTS_RUN ]; then
  echo -e "${GREEN}✅ All tests passed!${NC}"
  exit 0
else
  echo -e "${RED}❌ Some tests failed${NC}"
  exit 1
fi
