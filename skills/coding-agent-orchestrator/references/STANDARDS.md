# Coding Standards

## Contents
- Principles
- Size Limits
- Naming & Clarity
- Error Handling
- Testing
- Security
- Documentation

**Language:** English only - all code, comments, docs, examples, commits, configs, errors, tests

## Foundational Principles

**KISS (Keep It Simple)**
- Simplest solution wins | Avoid premature abstraction | Reduce complexity
- Inline single-use helpers | Remove unused flexibility | Flatten unnecessary layers

**YAGNI (You Aren't Gonna Need It)**
- Build only what's needed now | No speculative features | No "future-proofing"
- Delete unused code completely | Add complexity when required, not before

**DRY (Don't Repeat Yourself)**
- Extract common patterns | Maintain consistency | Single source of truth
- Three strikes rule - don't abstract until third occurrence

**SRP (Single Responsibility)**
- One class, one reason to change | One responsibility per module
- Separate authentication, database operations, business logic, UI concerns

## Design Principles

**Law of Demeter**
- Classes know only direct dependencies | Avoid chaining | "Don't talk to strangers"
- Add delegation methods | Pass required objects directly | Flatten access patterns

**Dependency Injection**
- Inject dependencies explicitly | Avoid hidden coupling | Make relationships visible
- Constructor injection for required dependencies | Method injection for optional

**Polymorphism over Conditionals**
- Prefer polymorphism to if/else chains | Use interfaces for extensibility
- Extract strategy pattern | Replace conditionals with polymorphic dispatch

## Size Limits & Refactoring Triggers

- **Functions**: Max 30-40 lines
- **Classes**: Max 500 lines | Refactor when >30 methods
- **Files**: Max 500 lines | Split when exceeding or mixing multiple concerns
- **Methods per Class**: Max 20-30 methods

## Refactoring Best Practices

- **Small Steps**: Incremental changes to reduce bugs | Test each modification
- **Separate Concerns**: Never mix refactoring with bug fixing
- **No Backwards-Compatibility Hacks**: Delete unused code completely | No renaming to _vars | No // removed comments

## Universal Coding Standards

- **Naming**: Descriptive, searchable names | Replace magic numbers with named constants
- **Functions**: Max 3-4 parameters | Encapsulate boundary conditions | Declare variables near usage
- **TypeScript**: Use Record<string, unknown> over any | PascalCase (classes/interfaces) | camelCase (functions/variables)
- **Error Handling**: Explicit error patterns | Never silent failures
- **Imports**: Order as node → external → internal | Remove unused immediately
- **Git Commits**: Conventional format: type(scope): subject | 50 chars max, imperative mood | Atomic changes
  - *Repo override:* If a repository defines a different format (e.g., `Type: Description #issue`), **follow the repo** and retain `#issue` linkage.

## Inclusive Language

- **Terms**: allowlist/blocklist, primary/replica, placeholder/example, main branch, conflict-free, concurrent/parallel

## Process Compliance Checks

During standards review, also verify process compliance:

### Git Workflow Compliance
- [ ] Changes made on feature branch (not main)
- [ ] PR exists with descriptive title
- [ ] Commits follow conventional format (`type(scope): description`)
- [ ] No force pushes to shared branches
- [ ] No direct commits to main
- [ ] PR/issue titles follow repo conventions
- [ ] PR body includes `What`, `Why`, `Tests`, `AI Assistance`
- [ ] `Tests` section lists exact commands run

### Tool Usage Compliance
- [ ] If agent CLI specified → verify CLI was used (look for CLI invocation in session log)
- [ ] Implementation done via agent CLI (Codex/Claude); direct CLI primary, tmux optional for durable runs (not direct file edits)
- [ ] Reviews done via `codex review` or `claude -p`
- [ ] Tool used is documented in PR description
- [ ] If AI-assisted, PR documents testing level and prompt/session log reference

### Review Process Compliance
- [ ] Code/logic review completed
- [ ] Standards review completed
- [ ] Both reviews posted to GitHub PR
- [ ] Self-audit completed (or explicit skip reason documented)
- [ ] Issues found are addressed before merge

### Compliance Review Output Format
```markdown
## Process Compliance Review ✅|❌

### Git Workflow
- [x] Feature branch used
- [x] PR created
- [x] Conventional commits

### Tool Usage
- [x] Specified tools used
- [x] Implementation via agent CLI (direct or tmux)

### Review Process
- [x] Code review posted
- [x] Standards review posted

**Status**: COMPLIANT / NON-COMPLIANT
```
