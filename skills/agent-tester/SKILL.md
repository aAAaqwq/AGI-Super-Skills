---
name: agent-tester
description: Test agent: dry-run, unit, integration, compatibility
---
# Agent Tester

> Tests a built agent: dry-run, unit tests, integration, compatibility with other agents.

## When to use

- After Agent Builder has finished
- "test agent X"
- "check agent compatibility"

## Input

- Agent from `$AGENTS_PATH/[name]/`
- Spec from `$AGENTS_PATH/specs/[name].spec.md`

## How to execute

### Step 1: Static analysis

Check the agent code:

- [ ] File exists and runs without syntax errors
- [ ] All imports resolve
- [ ] Config file is valid
- [ ] Paths in config exist
- [ ] Credentials are accessible
- [ ] Dry-run mode is implemented

### Step 2: Dry-run test

Run the agent with `--dry-run`:

```bash
python3 $AGENTS_PATH/[name]/[name]_agent.py --dry-run
```

Check:
- [ ] Agent starts without errors
- [ ] Logs are clear
- [ ] Shows what it WOULD do (without real side effects)
- [ ] Execution time is reasonable

### Step 3: Unit tests

Run tests:

```bash
python3 -m pytest $AGENTS_PATH/[name]/test_[name].py -v
```

Minimum tests:
- [ ] Input parsing works
- [ ] Business logic is correct on test data
- [ ] Error handling works (bad input, missing files, API timeout)
- [ ] Output format is correct

### Step 4: Integration test (one run on real data)

**WARNING: only with human approval!**

1. Back up data that the agent modifies:
```bash
cp [target.csv] [target.csv.backup]
```

2. Run the agent once on real data
3. Check output:
   - [ ] Data was written correctly
   - [ ] Format matches schema.yaml
   - [ ] Nothing broke
   - [ ] Git commit was created (if needed)

4. If something is wrong -- rollback:
```bash
cp [target.csv.backup] [target.csv]
```

### Step 5: Compatibility test

Check that the new agent does not conflict with existing ones:

```markdown
## Compatibility Matrix

| Agent | Shared Files | Potential Conflict | Status |
|-------|-------------|-------------------|--------|
| Email Pipeline | activities.csv | Write conflict | ? |
| [other agents] | ... | ... | ? |
```

Specific checks:
- [ ] **File locks**: can two agents write to the same CSV simultaneously
- [ ] **Data consistency**: does the agent overwrite another agent's data
- [ ] **ID generation**: do IDs conflict (person_id, activity_id, etc.)
- [ ] **Schedule overlap**: do agents run at the same time
- [ ] **Git conflicts**: does auto-commit create merge conflicts

### Step 6: Report

Create a test report file:

```
$AGENTS_PATH/specs/[name].test-report.md
```

**Report structure:**

```markdown
# Test Report: [Agent Name]

## Date: YYYY-MM-DD
## Tester: Process Analyst Agent

## Results

| Test | Status | Notes |
|------|--------|-------|
| Static analysis | PASS/FAIL | |
| Dry-run | PASS/FAIL | |
| Unit tests | PASS/FAIL | X/Y passed |
| Integration | PASS/FAIL | |
| Compatibility | PASS/FAIL | |

## Issues Found
1. [Issue description + severity]

## Recommendation
- [ ] READY for production
- [ ] NEEDS FIXES (list what)
- [ ] BLOCKED (list why)
```

## Output

- Test report in `$AGENTS_PATH/specs/[name].test-report.md`
- PASS/FAIL verdict
- List of issues if any

## Related skills

- `process-analyst` — creates the spec
- `agent-builder` — builds the agent
- `change-review` — validates CRM/PM changes
