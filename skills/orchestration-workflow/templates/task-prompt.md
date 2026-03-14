# Task: {{TITLE}}

## Requirements
{{REQUIREMENTS}}

## Engineering Standards (Non-negotiable)

### Phase 1: Research (BEFORE writing any code)
1. Read the files mentioned in Requirements
2. Understand the existing code structure and patterns
3. State your approach in 3 sentences
4. List your assumptions explicitly
5. If requirements conflict with existing code, note it in assumptions

### Phase 2: Implement
- Minimum code that solves the problem — nothing more
- Match the existing code style (indentation, naming, patterns)
- Only modify files listed in Requirements unless absolutely necessary
- If changes need >3 files, STOP and set `needs_split: true`

### Phase 3: Verify
- List 3 edge cases you considered
- Run build: `npm run build`
- Run tests if available: `npm test` or `npx vitest run`
- Check for regressions

### Build & Commit (CRITICAL — you MUST execute these commands)
The orchestration pipeline checks for a git commit. No commit = task rejected.
```bash
npm run build
npm test 2>/dev/null || true
git add -A
git reset HEAD .task-prompt.md .task-result.json CLAUDE.md 2>/dev/null || true
git commit -m "{{COMMIT_MSG}}"
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
  "test_pass": true or null,
  "needs_split": false,
  "approach": "3-sentence summary of what you did and why",
  "edge_cases": ["3 edge cases you considered"],
  "assumptions": ["assumptions you made"],
  "notes": "anything the orchestrator should know",
  "errors": ["any issues encountered"]
}
```
Do NOT commit `.task-prompt.md`, `.task-result.json`, or `CLAUDE.md`.
