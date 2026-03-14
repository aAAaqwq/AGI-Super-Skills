# Debug Task: {{TITLE}}

## Bug Description
{{BUG_DESCRIPTION}}

## Reproduction Steps
{{REPRO_STEPS}}

## Expected vs Actual Behavior
- **Expected**: {{EXPECTED}}
- **Actual**: {{ACTUAL}}

## Suspected Files
{{SUSPECTED_FILES}}

## Orchestrator Pre-Diagnosis
- **Console/Error Output**: {{ERROR_OUTPUT}}
- **Suspected Root Cause**: {{SUSPECTED_CAUSE}}
- **Confidence**: {{CONFIDENCE}}

## Previous Attempts (if retry)
{{PREVIOUS_ATTEMPTS}}

## Engineering Standards (Non-negotiable)

### Debug Protocol (MUST follow in order)
1. **REPRODUCE**: Write a failing test FIRST (before any code change)
2. **OBSERVE**: Add instrumentation if root cause unclear
3. **DIAGNOSE**: State root cause + evidence + confidence
4. **FIX**: Minimal surgical change (only root cause)
5. **VERIFY**: New test green + all old tests green + build pass
6. **CLEAN**: Remove all debug logs, keep the test

### Rules
- NO fix without a failing test first
- NO guess-fixes (if confidence is low, add more instrumentation)
- NO modifying old tests to match your fix
- NO "while I'm here" refactoring
- Max 3 fix attempts, then report failure
- If fix needs >3 files, mark `needs_split: true`

### Build & Commit (CRITICAL — you MUST execute)
```bash
npm test              # ALL tests must pass
npm run build         # Must succeed
git add -A
git reset HEAD .task-prompt.md .task-result.json CLAUDE.md 2>/dev/null || true
git commit -m "fix: {{COMMIT_MSG}}

Root cause: [one line]
Test: [test file::test name]"
```

## Output Protocol (MUST follow)
Create `.task-result.json` AFTER committing:
```json
{
  "status": "success or failed",
  "files_created": ["list"],
  "files_modified": ["list"],
  "commit": "short hash from git log --oneline -1",
  "build_pass": true,
  "test_pass": true,
  "root_cause": "One sentence WHY",
  "evidence": "What confirmed diagnosis",
  "confidence": "high|medium|low",
  "debug_attempts": 1,
  "test_added": "path/to/test.ts::test name",
  "approach": "3-sentence summary",
  "edge_cases": ["edge cases"],
  "assumptions": ["assumptions"],
  "errors": []
}
```
Do NOT commit `.task-prompt.md`, `.task-result.json`, or `CLAUDE.md`.
