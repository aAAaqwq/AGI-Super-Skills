# Debug-with-TDD: Automated Bug Fix Protocol

You are in **autonomous debug mode**. No human will intervene.
You must fix the bug AND prove it's fixed, all in one session.

## The Loop (mandatory, no shortcuts)

```
Step 1: REPRODUCE → Write a failing test
Step 2: OBSERVE   → Add instrumentation if needed
Step 3: DIAGNOSE  → Find root cause (not symptoms)
Step 4: FIX       → Minimal surgical fix
Step 5: VERIFY    → All tests green (old + new)
Step 6: CLEAN     → Remove debug instrumentation
```

## Step 1: REPRODUCE (Write the Failing Test FIRST)

Before touching any production code:

1. Read the bug description carefully
2. Identify the exact failure condition
3. Write a **minimal test** that reproduces the bug:
   - Unit test if it's a logic bug
   - Integration test if it involves multiple components
   - The test MUST fail before your fix (Red)
4. Run the test, confirm it fails with the expected error

```bash
# Run just your new test
npm test -- --grep "should handle [bug scenario]"
# or for specific file
npx jest path/to/bug.test.ts
```

**If you can't write a test** (UI-only bug, environment-specific):
- Write a script that checks the condition programmatically
- Document WHY a test isn't possible in .task-result.json

## Step 2: OBSERVE (Add Instrumentation)

If the root cause isn't obvious from the failing test:

1. Add `console.log` / `console.error` at suspected points
2. Log input values, intermediate state, return values
3. Run the failing test again with instrumentation
4. Read the output carefully

**Format your logs clearly:**
```typescript
console.log('[DEBUG] functionName:', { input, intermediateValue, output });
```

## Step 3: DIAGNOSE (Root Cause, Not Symptoms)

Before writing any fix, you MUST state:

```
ROOT CAUSE: [one sentence explaining WHY the bug exists]
EVIDENCE: [what you observed that confirms this]
CONFIDENCE: high | medium | low
```

**If confidence is LOW:**
- Add more instrumentation (back to Step 2)
- Do NOT guess-fix

**Common traps to avoid:**
- "It works if I add a null check" → WHY is it null? Fix that.
- "It works if I add a timeout" → WHY is it timing out? Fix that.
- "It works if I change the order" → WHY does order matter? Document that.

## Step 4: FIX (Minimal Surgical Change)

Rules:
- Fix ONLY the root cause identified in Step 3
- Do NOT refactor unrelated code
- Do NOT add "while I'm here" improvements
- If fix requires changing >3 files, stop and note `needs_split: true`

## Step 5: VERIFY (All Tests Green)

```bash
# 1. Run your new test (should now PASS - Green)
npm test -- --grep "should handle [bug scenario]"

# 2. Run ALL tests (no regressions)
npm test

# 3. Run build
npm run build

# 4. Run lint (if available)
npm run lint 2>/dev/null || true
```

**If any OLD test fails after your fix:**
- Your fix has a side effect
- Do NOT modify old tests to match your fix
- Re-diagnose (back to Step 3)

**Retry loop (max 3 attempts):**
If your fix doesn't make the test green:
1. Re-read the test output
2. Re-diagnose (was root cause wrong?)
3. Revert your fix: `git checkout -- .`
4. Try again from Step 3

After 3 failed attempts, stop and report in .task-result.json:
```json
{ "status": "failed", "debug_attempts": 3, "last_diagnosis": "..." }
```

## Step 6: CLEAN (Remove Debug Code)

Before committing:
1. Remove ALL `console.log('[DEBUG]` lines you added
2. Remove any temporary instrumentation
3. Keep the new test (it's the proof)
4. `git diff` to verify only intentional changes remain

## Commit

```bash
git add -A
git reset HEAD .task-prompt.md .task-result.json CLAUDE.md 2>/dev/null || true
git commit -m "fix: [description of what was fixed]

Root cause: [one line]
Test: [test file and test name]"
```

## Output (.task-result.json)

```json
{
  "status": "success or failed",
  "files_created": [],
  "files_modified": [],
  "commit": "short hash",
  "build_pass": true,
  "test_pass": true,
  "root_cause": "One sentence explaining WHY",
  "evidence": "What confirmed the diagnosis",
  "confidence": "high|medium|low",
  "debug_attempts": 1,
  "test_added": "path/to/test.ts::test name",
  "approach": "3-sentence summary of the fix",
  "edge_cases": ["edge cases considered"],
  "assumptions": ["assumptions made"],
  "errors": []
}
```

## What "Fixed" Means (Acceptance Criteria)

A bug is fixed ONLY when ALL of these are true:
- [ ] New test exists that reproduces the original bug
- [ ] New test passes after fix
- [ ] All pre-existing tests still pass
- [ ] Build succeeds
- [ ] Root cause is documented (not just "added null check")
- [ ] No debug instrumentation left in code
- [ ] Fix is minimal (no unrelated changes)
