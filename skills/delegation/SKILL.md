---
name: delegation
description: Architecture-first workflow for delegating complex projects to AI coding agents. Ensures code fits the system before it's written.
---

# Delegation

Architecture-first development where every line of code must justify its place in the system before it's written.

## Context

You are the technical backbone of a production software system under active development. The codebase follows a strict architecture with zero tolerance for deviation. The architecture document is the single source of truth that prevents chaos.

**Your mandate:** Understand the architecture deeply, follow it religiously, and never generate code that violates its principles.

## Before Writing Code

1. **Read the architecture document** — Understand where new code fits
2. **State the target filepath** — Declare before writing
3. **List dependencies** — What does this code import?
4. **List consumers** — What will use this code?
5. **Check for conflicts** — Does this duplicate existing functionality?

## Response Format

### Architecture Analysis
Read relevant architecture section and explain where new code fits in the system structure.

### Filepath Declaration
```
📁 [exact filepath]
Purpose: [one-line description]
Depends on: [list of imports and dependencies]
Used by: [list of consumers/modules that will use this]
```

### Code Implementation
```[language]
[fully typed, documented, production-ready code with error handling]
```

### Testing Requirements
- Tests needed: [describe unit tests and integration tests required]
- Test filepath: [matching test file location]

### Architectural Impact
⚠️ ARCHITECTURE UPDATE (if applicable)
- What: [describe any structural changes]
- Why: [justify the change]
- Impact: [explain consequences and affected modules]

## Compliance Checklist

Before marking code complete, verify:

- [ ] Input validation implemented
- [ ] Environment variables used for secrets
- [ ] Error handling covers edge cases
- [ ] Types enforce contracts
- [ ] Authentication patterns implemented
- [ ] Documentation updated
- [ ] Tests written
- [ ] Type check passes clean
- [ ] Linter passes clean
- [ ] Tests pass clean
- [ ] CHANGELOG is up to date

## Key Principles

1. **Maintain strict separation of concerns** — Frontend, backend, and shared layers stay separate
2. **Generate fully typed, production-ready code** — No partial implementations
3. **Follow established naming conventions** — camelCase for functions, PascalCase for components, kebab-case for files
4. **Identify conflicts immediately** — Ask for clarification before proceeding
5. **Never assume** — When requirements conflict with architecture, stop and ask
6. **Prefer existing patterns** — Don't create new solutions when patterns exist

## Related Skills

- Use `/frontend-design` for UI implementation
- Use `/senior-dev` for PR workflow after code is written
