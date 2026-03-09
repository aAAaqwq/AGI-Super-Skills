# Violation Examples and Recovery

## Violation Consequences

If any rule is violated:
1. Stop immediately.
2. Acknowledge the violation.
3. Revert or fix.
4. Document the violation in PR/commit notes.
5. Resume correctly.

## Common Pitfalls

### ❌ Writing code directly
Wrong:
```bash
Edit file.py: add function xyz...
```
Correct:
```bash
./scripts/code-implement "Add function xyz to file.py"
```

### ❌ Skipping review
Wrong:
```bash
git push && gh pr create && gh pr merge
```
Correct:
```bash
gh pr create
timeout 600s codex review --base <base> --title "PR Review"
./scripts/tmux-run timeout 1200s codex --yolo exec -c model_reasoning_effort="medium" \
  "Review against STANDARDS.md and report PASS/FAIL per category"
```

### ❌ Chaining without timeouts
Wrong:
```bash
codex exec "Part 1" && codex exec "Part 2"
```
Correct:
```bash
timeout 300s codex --yolo exec -c model_reasoning_effort="high" "Part 1"
timeout 300s codex --yolo exec -c model_reasoning_effort="high" "Part 2"
```

## Real Violation Examples

### Example 1: “Trivial Change” Rationalization
- What happened: Direct edit for a typo.
- Why wrong: Rule 1 has no exceptions.
- Fix:
```bash
./scripts/code-implement "Fix typo in config.py line 42"
```

### Example 2: Skipped PR Creation
- What happened: Commit on main, pushed directly.
- Why wrong: Rule 2 and Rule 3.
- Fix:
```bash
git checkout -b fix/typo-config
git add -A && git commit -m "fix: correct typo"
git push -u origin fix/typo-config
gh pr create
```

### Example 3: Missing Self-Check
- What happened: Implementation started without STOP-AND-VERIFY.
- Why wrong: Mandatory protocol.
- Fix: perform STOP-AND-VERIFY before any changes.
