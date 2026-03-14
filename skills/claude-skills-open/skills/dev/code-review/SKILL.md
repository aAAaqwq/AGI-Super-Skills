---
name: code-review
description: AI code review for PR or local changes
---
# Code Review

> Comprehensive AI-powered code review for PRs and local changes — enterprise-grade alternative to CodeRabbit

## When to use

- "code review"
- "review my PR"
- "review PR #123"
- "check my changes"
- "what's wrong with my code"
- "security review"
- "full review"
- "/review"
- "/review-pr"

## Dependencies

- External: `gh` CLI (GitHub), `git`

## Modes

### 1. Local review (uncommitted changes)
Reviews `git diff` — changes not yet committed.

### 2. Branch review (vs main/master)
Reviews all changes in current branch compared to main.

### 3. PR review (GitHub)
Fetches diff from GitHub PR and can post comments.

### 4. Focused review
User can request specific focus: security, performance, bugs, style, etc.

---

## How to execute

### Step 0: Check if review needed

**Skip review if:**
- PR is draft (`gh pr view --json isDraft`)
- PR is already closed/merged
- Only documentation changes (.md, .txt, LICENSE)
- Only config changes (.json, .yaml, .toml) without code impact
- Trivial changes (<5 lines, whitespace only, version bumps)

**Inform user and ask to confirm if they still want review.**

---

### Step 1: Determine mode

Ask user or detect automatically:
- If PR number provided → PR review
- If uncommitted changes exist → local review
- If on feature branch → branch review
- If specific focus requested → apply focus filter

### Step 2: Get diff

**Local:**
```bash
git diff HEAD
```

**Branch (vs main):**
```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
git diff $DEFAULT_BRANCH...HEAD
```

**PR:**
```bash
gh pr diff <PR_NUMBER>
```

### Step 3: Get context

For thorough review, read related files:
```bash
# List changed files
git diff --name-only HEAD

# Read each file fully for context
# Check package.json for dependencies
# Check tsconfig/eslint config for project standards
```

### Step 3b: Filter pre-existing issues

Before reporting an issue, check if it was introduced in this PR:

```bash
# Check when the problematic line was last modified
git blame -L <start>,<end> <file> --porcelain | head -1
```

**Skip issues that:**
- Existed before this PR (old blame hash)
- Are in unchanged lines
- Were introduced by a different author long ago

**Only report issues introduced or modified in current changes.**

This prevents noise from legacy code and focuses review on new changes.

---

### Step 4: Comprehensive Analysis

Apply ALL relevant checks from the checklist below.

### Step 5: Confidence Scoring

**Rate each issue 0-100:**

| Score | Confidence | When to use |
|-------|------------|-------------|
| 90-100 | Certain | Clear vulnerability (SQL injection with user input), obvious crash |
| 70-89 | High | Likely bug, security risk, definite code smell |
| 50-69 | Medium | Potential issue, needs context to confirm |
| 25-49 | Low | Style preference, minor suggestion |
| 0-24 | Skip | Probably false positive, pre-existing, or nitpick |

**Only report issues with confidence ≥70.**

**Mark as false positive and skip:**
- Pre-existing issues (caught by Step 3b)
- Issues that linters will catch (eslint, prettier)
- Pedantic nitpicks without real impact
- Code that looks wrong but has valid reason (check comments)
- Issues with explicit ignore comments (`// eslint-disable`, `# noqa`)

---

### Step 6: Output result

**Format:**
```markdown
## Code Review Summary

**Reviewed:** X files, Y lines changed
**Risk Level:** Critical / High / Medium / Low

### Critical Issues (must fix)
- [file:line] Description — Why it matters

### High Priority
- [file:line] Description

### Medium Priority
- [file:line] Description

### Low Priority / Suggestions
- [file:line] Description

### Good Practices
- What was done well
```

**For GitHub PR — post comments:**
```bash
# General comment on PR
gh pr comment <PR_NUMBER> --body "## AI Code Review
[Review content]"

# Line-by-line comments via API (for specific file/line feedback)
# Replace {owner}, {repo}, {pr} with actual values
gh api repos/{owner}/{repo}/pulls/{pr}/comments \
  --method POST \
  -f body="Issue description and fix suggestion" \
  -f path="src/file.ts" \
  -f line=42 \
  -f side="RIGHT"
```

---

## COMPREHENSIVE REVIEW CHECKLIST

### 1. SECURITY (OWASP Top 10 + Extended)

#### 1.1 Injection
- [ ] **SQL Injection** — User input in SQL queries without parameterization
- [ ] **NoSQL Injection** — Unsanitized input in MongoDB/similar queries
- [ ] **Command Injection** — User input passed to shell commands (exec, spawn, system)
- [ ] **LDAP Injection** — User input in LDAP queries
- [ ] **XPath Injection** — User input in XML queries
- [ ] **Template Injection** — User input in template engines (SSTI)
- [ ] **Header Injection** — User input in HTTP headers (CRLF)
- [ ] **Log Injection** — Unsanitized data written to logs

#### 1.2 Broken Authentication
- [ ] **Weak password requirements** — No complexity enforcement
- [ ] **Missing brute-force protection** — No rate limiting on login
- [ ] **Session fixation** — Session ID not regenerated after login
- [ ] **Insecure session storage** — Sessions in localStorage (XSS vulnerable)
- [ ] **Missing logout** — No session invalidation
- [ ] **Predictable tokens** — Using weak random generators for tokens
- [ ] **Password in URL** — Credentials in query parameters
- [ ] **Missing MFA on critical operations** — No 2FA for sensitive actions

#### 1.3 Sensitive Data Exposure
- [ ] **Hardcoded secrets** — API keys, passwords, tokens in code
- [ ] **Secrets in logs** — Sensitive data written to console/logs
- [ ] **Secrets in error messages** — Stack traces exposing internals
- [ ] **Unencrypted sensitive data** — PII/credentials not encrypted at rest
- [ ] **Weak cryptography** — MD5, SHA1 for passwords, short keys
- [ ] **Missing HTTPS** — HTTP links for sensitive operations
- [ ] **Sensitive data in URLs** — Tokens/IDs in GET parameters
- [ ] **Excessive data exposure** — Returning more fields than needed in API

#### 1.4 XML External Entities (XXE)
- [ ] **XML parsing without disabling DTD** — External entity processing enabled
- [ ] **Unsafe XML deserialization** — User-controlled XML parsed

#### 1.5 Broken Access Control
- [ ] **Missing authorization checks** — Actions without permission verification
- [ ] **IDOR (Insecure Direct Object Reference)** — Accessing resources by ID without ownership check
- [ ] **Privilege escalation** — User can access admin functions
- [ ] **CORS misconfiguration** — Wildcard or overly permissive origins
- [ ] **Missing function-level access control** — API endpoints without role checks
- [ ] **Path traversal** — User input in file paths (../)
- [ ] **Forced browsing** — Unprotected admin/debug endpoints

#### 1.6 Security Misconfiguration
- [ ] **Debug mode in production** — Verbose errors, stack traces exposed
- [ ] **Default credentials** — Unchanged default passwords
- [ ] **Unnecessary features enabled** — Unused endpoints, methods
- [ ] **Missing security headers** — No CSP, X-Frame-Options, etc.
- [ ] **Directory listing enabled** — Exposed file structure
- [ ] **Outdated dependencies** — Known vulnerabilities in packages
- [ ] **Permissive file permissions** — World-readable sensitive files

#### 1.7 Cross-Site Scripting (XSS)
- [ ] **Reflected XSS** — User input echoed without encoding
- [ ] **Stored XSS** — Database content rendered without sanitization
- [ ] **DOM XSS** — Client-side JS using unsafe sinks (innerHTML, eval)
- [ ] **Missing Content-Security-Policy** — No CSP headers
- [ ] **Unsafe React patterns** — dangerouslySetInnerHTML with user content
- [ ] **Template literal injection** — User input in template strings

#### 1.8 Insecure Deserialization
- [ ] **Unsafe JSON parsing** — eval() for JSON
- [ ] **Object deserialization** — pickle, serialize without validation
- [ ] **Prototype pollution** — Object.assign/merge with user input

#### 1.9 Using Components with Known Vulnerabilities
- [ ] **Outdated dependencies** — Check package.json against vulnerability databases
- [ ] **Abandoned packages** — Dependencies with no recent updates
- [ ] **Typosquatting** — Suspicious package names

#### 1.10 Insufficient Logging & Monitoring
- [ ] **Missing audit logs** — No logging for security events
- [ ] **Missing error handling** — Silent failures
- [ ] **No alerting** — Security events not monitored

#### 1.11 Additional Security Checks
- [ ] **SSRF (Server-Side Request Forgery)** — User-controlled URLs in server requests
- [ ] **Open Redirect** — User input in redirect URLs
- [ ] **CSRF protection missing** — No tokens for state-changing operations
- [ ] **JWT issues** — Weak secret, algorithm confusion, no expiry
- [ ] **Regex DoS (ReDoS)** — Catastrophic backtracking in regex
- [ ] **Mass assignment** — Binding request body directly to models
- [ ] **File upload vulnerabilities** — No type validation, path traversal
- [ ] **Race conditions** — TOCTOU (time-of-check-time-of-use) issues

---

### 2. BUGS & LOGIC ERRORS

#### 2.1 Null/Undefined Handling
- [ ] **Null pointer dereference** — Accessing properties of null/undefined
- [ ] **Missing null checks** — Optional chaining not used where needed
- [ ] **Null coalescing issues** — Wrong default values
- [ ] **Falsy value confusion** — 0, '', false treated as null

#### 2.2 Type Issues
- [ ] **Type coercion bugs** — == instead of ===
- [ ] **Implicit type conversion** — String + Number concatenation
- [ ] **Missing type checks** — typeof/instanceof not used
- [ ] **Type assertion abuse** — Unsafe 'as' casts in TypeScript
- [ ] **Any type overuse** — Losing type safety

#### 2.3 Async/Concurrency
- [ ] **Missing await** — Unhandled promises
- [ ] **Unhandled promise rejection** — No .catch() or try/catch
- [ ] **Race conditions** — Shared state without synchronization
- [ ] **Deadlocks** — Circular waiting for resources
- [ ] **Callback hell** — Nested callbacks instead of async/await
- [ ] **Memory leaks from listeners** — Event listeners not removed
- [ ] **Stale closures** — Capturing old values in closures

#### 2.4 Loop/Iteration Errors
- [ ] **Off-by-one errors** — Wrong loop bounds
- [ ] **Infinite loops** — Missing break condition
- [ ] **Mutating while iterating** — Modifying collection during loop
- [ ] **Wrong loop variable** — Using outer variable in nested loop
- [ ] **forEach with async** — Not waiting for async operations

#### 2.5 Boundary/Edge Cases
- [ ] **Empty array/object** — Not handling empty collections
- [ ] **Single element** — Edge case for arrays with one item
- [ ] **Negative numbers** — Not handling negative input
- [ ] **Zero division** — Dividing without checking denominator
- [ ] **Integer overflow** — Large number calculations
- [ ] **Floating point precision** — 0.1 + 0.2 !== 0.3
- [ ] **Unicode/encoding** — Special characters not handled
- [ ] **Timezone issues** — Date handling without timezone awareness
- [ ] **Daylight saving time** — Date calculations across DST

#### 2.6 State Management
- [ ] **Stale state** — React setState with stale closure
- [ ] **Missing state updates** — UI not reflecting state
- [ ] **State mutation** — Direct state modification
- [ ] **Prop drilling issues** — Props passed too deep
- [ ] **Unnecessary re-renders** — Missing memoization

#### 2.7 Error Handling
- [ ] **Empty catch blocks** — Swallowing errors silently
- [ ] **Generic error handling** — Catching all without specificity
- [ ] **Missing finally** — Resources not cleaned up
- [ ] **Rethrowing without context** — Losing stack trace
- [ ] **Error in error handler** — Handler itself can throw

#### 2.8 Resource Management
- [ ] **Resource leaks** — Files, connections not closed
- [ ] **Memory leaks** — Objects not garbage collected
- [ ] **Connection pool exhaustion** — Not returning connections
- [ ] **File handle leaks** — Streams not closed
- [ ] **Timer leaks** — setInterval not cleared

#### 2.9 Business Logic
- [ ] **Wrong calculations** — Incorrect formulas
- [ ] **Missing validation** — Business rules not enforced
- [ ] **State machine violations** — Invalid state transitions
- [ ] **Duplicate operations** — Same action performed twice
- [ ] **Missing rollback** — Partial updates on failure

---

### 3. PERFORMANCE

#### 3.1 Database
- [ ] **N+1 queries** — Loop with individual queries
- [ ] **Missing indexes** — Queries on unindexed columns
- [ ] **SELECT *** — Fetching unnecessary columns
- [ ] **Missing pagination** — Loading all records
- [ ] **Missing connection pooling** — New connection per request
- [ ] **Expensive JOINs** — Large table joins without optimization
- [ ] **Missing query caching** — Repeated identical queries
- [ ] **Transaction scope too large** — Holding locks too long
- [ ] **Inefficient aggregations** — COUNT/SUM without indexes

#### 3.2 API/Network
- [ ] **Missing caching** — No Cache-Control headers
- [ ] **Over-fetching** — Returning more data than needed
- [ ] **Under-fetching** — Multiple requests for related data
- [ ] **No compression** — Missing gzip/brotli
- [ ] **Chatty APIs** — Too many small requests
- [ ] **Missing pagination** — Large response payloads
- [ ] **Synchronous external calls** — Blocking on I/O
- [ ] **Missing timeouts** — No timeout on HTTP calls
- [ ] **Missing retry logic** — No retry for transient failures

#### 3.3 Frontend
- [ ] **Large bundle size** — Missing code splitting
- [ ] **Render blocking resources** — CSS/JS blocking paint
- [ ] **Unnecessary re-renders** — Missing React.memo, useMemo
- [ ] **Large images** — Unoptimized images
- [ ] **Missing lazy loading** — Loading offscreen content
- [ ] **Layout thrashing** — Forced synchronous layouts
- [ ] **Heavy animations** — Expensive CSS/JS animations
- [ ] **Memory leaks** — Detached DOM nodes
- [ ] **Long tasks** — Blocking main thread >50ms

#### 3.4 Algorithms
- [ ] **O(n²) or worse** — Nested loops on large data
- [ ] **Repeated calculations** — No memoization
- [ ] **String concatenation in loops** — Using += for strings
- [ ] **Inefficient data structures** — Array instead of Set/Map
- [ ] **Unnecessary copying** — Deep clone when not needed
- [ ] **Redundant sorting** — Sorting already sorted data

#### 3.5 Caching
- [ ] **Missing caching layer** — No Redis/Memcached
- [ ] **Cache invalidation issues** — Stale data served
- [ ] **Cache stampede** — Many requests on cache miss
- [ ] **No cache warming** — Cold start performance
- [ ] **Unbounded cache** — No eviction policy

---

### 4. CODE QUALITY

#### 4.1 Readability
- [ ] **Poor naming** — Unclear variable/function names
- [ ] **Magic numbers** — Hardcoded values without constants
- [ ] **Long functions** — Functions >50 lines
- [ ] **Deep nesting** — >3 levels of indentation
- [ ] **Complex conditionals** — Hard to understand if/else chains
- [ ] **Missing comments for complex logic** — Unclear algorithms
- [ ] **Inconsistent naming convention** — camelCase mixed with snake_case
- [ ] **Abbreviations** — Unclear shortened names

#### 4.2 Maintainability
- [ ] **DRY violations** — Copy-pasted code
- [ ] **God objects/functions** — Doing too much
- [ ] **Tight coupling** — Hard dependencies between modules
- [ ] **Missing abstraction** — Repeated patterns not extracted
- [ ] **Premature abstraction** — Over-engineering simple code
- [ ] **Circular dependencies** — Modules importing each other
- [ ] **Dead code** — Unused functions, variables, imports
- [ ] **Commented-out code** — Old code left in comments
- [ ] **TODO/FIXME/HACK** — Technical debt markers

#### 4.3 SOLID Principles
- [ ] **Single Responsibility** — Class/function doing multiple things
- [ ] **Open/Closed** — Modifying instead of extending
- [ ] **Liskov Substitution** — Subclasses breaking parent contract
- [ ] **Interface Segregation** — Fat interfaces
- [ ] **Dependency Inversion** — Depending on concretions

#### 4.4 Error Messages
- [ ] **Generic error messages** — "Something went wrong"
- [ ] **Technical jargon for users** — Stack traces shown to users
- [ ] **Missing error codes** — No way to identify errors
- [ ] **Non-actionable errors** — User doesn't know what to do

#### 4.5 API Design
- [ ] **Inconsistent response format** — Different structures per endpoint
- [ ] **Wrong HTTP methods** — POST for GET operations
- [ ] **Wrong status codes** — 200 for errors
- [ ] **Missing versioning** — No API version in path/header
- [ ] **Breaking changes** — Removing/renaming fields
- [ ] **Missing documentation** — No OpenAPI/Swagger

#### 4.6 Configuration
- [ ] **Hardcoded configuration** — No environment variables
- [ ] **Missing defaults** — Required config without fallback
- [ ] **Scattered config** — Configuration in multiple places
- [ ] **Secrets in config files** — Credentials in committed files

---

### 5. TESTING

#### 5.1 Test Coverage
- [ ] **Missing unit tests** — Critical functions untested
- [ ] **Missing integration tests** — API endpoints untested
- [ ] **Missing edge case tests** — Only happy path tested
- [ ] **Missing error case tests** — Error handling untested
- [ ] **Low coverage on changed files** — New code not tested

#### 5.2 Test Quality
- [ ] **Flaky tests** — Tests that sometimes fail
- [ ] **Slow tests** — Tests taking too long
- [ ] **Test interdependence** — Tests depending on order
- [ ] **Missing assertions** — Tests without expect/assert
- [ ] **Testing implementation** — Testing how, not what
- [ ] **Mocking too much** — Testing mocks, not code
- [ ] **Missing test data cleanup** — Side effects between tests

#### 5.3 Test Patterns
- [ ] **Missing describe blocks** — No test organization
- [ ] **Unclear test names** — "test1", "should work"
- [ ] **Arrange-Act-Assert** — Unclear test structure
- [ ] **Missing fixtures** — Repeated test data setup

---

### 6. ACCESSIBILITY (a11y)

- [ ] **Missing alt text** — Images without alt attributes
- [ ] **Missing form labels** — Inputs without labels
- [ ] **Color contrast** — Insufficient contrast ratio
- [ ] **Keyboard navigation** — Not usable without mouse
- [ ] **Missing ARIA labels** — Interactive elements without labels
- [ ] **Focus management** — Focus not handled in modals/SPAs
- [ ] **Missing skip links** — No way to skip navigation
- [ ] **Missing heading hierarchy** — Improper h1-h6 usage
- [ ] **Auto-playing media** — No way to stop audio/video
- [ ] **Missing screen reader text** — Icons without labels

---

### 7. INTERNATIONALIZATION (i18n)

- [ ] **Hardcoded strings** — Text not in translation files
- [ ] **Date/time formatting** — Not using locale-aware formatting
- [ ] **Number formatting** — Not handling decimal separators
- [ ] **Currency formatting** — Not handling currency symbols
- [ ] **RTL support** — Not handling right-to-left languages
- [ ] **Pluralization** — Not handling singular/plural
- [ ] **String concatenation** — Building sentences from parts
- [ ] **Hardcoded date formats** — MM/DD/YYYY vs DD/MM/YYYY

---

### 8. DOCUMENTATION

- [ ] **Missing README** — No project documentation
- [ ] **Outdated documentation** — Docs don't match code
- [ ] **Missing API docs** — No endpoint documentation
- [ ] **Missing JSDoc/TSDoc** — Public APIs undocumented
- [ ] **Missing changelog** — No record of changes
- [ ] **Missing setup instructions** — Hard to get started
- [ ] **Broken links** — Dead URLs in README, docs, or code comments
- [ ] **Relative link errors** — Wrong paths to internal docs/files

---

### 9. DEVOPS / INFRASTRUCTURE

- [ ] **Missing health checks** — No /health endpoint
- [ ] **Missing graceful shutdown** — Not handling SIGTERM
- [ ] **Missing retry logic** — No resilience patterns
- [ ] **Missing circuit breaker** — No failure isolation
- [ ] **Logging not structured** — Plain text instead of JSON
- [ ] **Missing correlation IDs** — Can't trace requests
- [ ] **Missing metrics** — No observability
- [ ] **Missing alerts** — No monitoring
- [ ] **Container issues** — Running as root, large images
- [ ] **Missing resource limits** — No CPU/memory limits

---

### 10. GIT/VERSION CONTROL

- [ ] **Large files committed** — Binary files, node_modules
- [ ] **Secrets in history** — API keys in past commits
- [ ] **Merge conflicts markers** — Unresolved conflicts
- [ ] **Mixed line endings** — CRLF/LF issues
- [ ] **Missing .gitignore entries** — Temporary files tracked
- [ ] **Large commits** — Too many changes in one commit
- [ ] **Unclear commit messages** — "fix", "update", "wip"

---

## LANGUAGE-SPECIFIC CHECKS (apply if relevant files detected)

### 11. REACT / NEXT.JS (if .tsx, .jsx files)

- [ ] **useEffect missing deps** — Dependencies array incomplete or missing
- [ ] **useEffect cleanup** — Missing cleanup for subscriptions, timers
- [ ] **useState stale closure** — Using state in callbacks without functional update
- [ ] **Key prop issues** — Missing key, using index as key in dynamic lists
- [ ] **useMemo/useCallback overuse** — Premature optimization
- [ ] **Prop drilling** — Props passed through many levels (use context)
- [ ] **Component too large** — >300 lines, should be split
- [ ] **Inline function in JSX** — Creating new function on every render
- [ ] **Direct DOM manipulation** — Using document.querySelector in React
- [ ] **Missing error boundary** — No error handling for component tree

### 12. TYPESCRIPT (if .ts, .tsx files)

- [ ] **Any type abuse** — Using `any` to bypass type checking
- [ ] **Type assertion abuse** — Unsafe `as` casts without validation
- [ ] **Missing return types** — Public functions without explicit return type
- [ ] **Implicit any** — Variables without type annotation
- [ ] **Non-null assertion** — Overuse of `!` operator
- [ ] **Enum vs union** — Using enum where union type is better
- [ ] **Unused exports** — Exported types/functions never imported

### 13. PYTHON (if .py files)

- [ ] **Mutable default args** — `def foo(items=[])` anti-pattern
- [ ] **Missing type hints** — Public functions without annotations
- [ ] **Bare except** — `except:` without specific exception
- [ ] **Context manager** — File/connection not using `with`
- [ ] **Global state** — Modifying global variables
- [ ] **Import side effects** — Code execution at import time
- [ ] **f-string security** — User input in f-strings (potential injection)

### 14. NODE.JS / EXPRESS (if package.json with express)

- [ ] **Async error handling** — Missing try/catch in async routes
- [ ] **Missing helmet** — No security headers middleware
- [ ] **Missing rate limiting** — No protection against abuse
- [ ] **Callback hell** — Nested callbacks instead of async/await
- [ ] **Blocking event loop** — Sync operations in request handlers
- [ ] **Missing input validation** — No validation middleware (joi, zod)
- [ ] **Hardcoded CORS** — Wildcard or hardcoded origins

### 15. SQL / DATABASE (if .sql files or ORM usage)

- [ ] **Raw queries** — String concatenation instead of parameterized
- [ ] **Missing indexes** — Queries on frequently filtered columns
- [ ] **N+1 in ORM** — Lazy loading in loops
- [ ] **Wide transactions** — Transaction scope too large
- [ ] **Missing migrations** — Schema changes without migration files
- [ ] **Cascading deletes** — Unintended data loss on delete

---

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `PR_NUMBER` | Pull Request number | - |
| `--post` | Post comments to GitHub | false |
| `--severity` | Minimum level (critical/high/medium/low) | low |
| `--focus` | Focus area: security, performance, bugs, quality, testing, a11y, i18n, all | all |

## Examples

### Example 1: Full review

```
User: full code review

Claude: [git diff HEAD]
Claude: [comprehensive analysis using all checklists]
Claude:
## Code Review Summary

**Reviewed:** 5 files, 234 lines changed
**Risk Level:** High

### Critical Issues (2)
1. [src/api/auth.ts:45] SQL Injection - User input passed directly to query
2. [src/utils/crypto.ts:12] Weak cryptography - Using MD5 for password hashing

### High Priority (3)
1. [src/services/user.ts:78] Missing authorization check - IDOR vulnerability
2. [src/api/data.ts:23] N+1 query - 50 queries in loop
3. [src/components/Form.tsx:156] XSS - dangerouslySetInnerHTML with user content

### Medium Priority (5)
...
```

### Example 2: Security-focused review

```
User: security review PR 123

Claude: [applies only security checklist]
Claude: Found 3 security issues...
```

### Example 3: Performance review

```
User: check performance issues in my changes

Claude: [applies only performance checklist]
Claude: Found 2 performance issues...
```

---

## Severity Levels

| Level | Description | Examples |
|-------|-------------|----------|
| **Critical** | Must fix before merge. Security vulnerabilities, data loss risks | SQL injection, hardcoded secrets, auth bypass |
| **High** | Should fix before merge. Significant bugs or security issues | N+1 queries, XSS, missing error handling |
| **Medium** | Fix soon. Code quality, minor bugs | DRY violations, missing tests, complexity |
| **Low** | Nice to have. Suggestions, style | Naming, comments, minor optimizations |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `gh: command not found` | `brew install gh && gh auth login` |
| No diff output | Check if changes exist: `git status` |
| PR not found | Check PR number and access rights |
| Can't post comments | Check permissions: `gh auth status` |
| Review too long | Use `--focus` to narrow scope |
| False positives | Mention specific context to skip |

---

## Limitations

- Static analysis only — cannot run code
- Cannot see runtime behavior
- May miss complex cross-file issues
- Needs context for architectural decisions
- GitHub API rate limits when posting many comments
- Language-specific checks may vary in depth

---

## If you're getting false positives

### Step 1: Use severity filter

Most false positives are low/medium severity. Start with high-only:

```text
"review PR 123 --severity=high"
"review my changes, only critical and high issues"
```

### Step 2: Use focus filter

Narrow to specific categories you care about:

```text
"security review PR 123"
"review PR 123 --focus=bugs,security"
"check only performance issues"
```

### Step 3: Tell Claude to skip specific issues

In the same conversation, provide context:

```text
"ignore the N+1 warning in admin routes - it's intentional, low traffic"
"skip any type warnings in src/legacy/ - that's legacy code"
"the raw SQL in migrations/ is fine, we use raw migrations"
```

### Step 4: Add inline comment in code

For persistent false positives that keep appearing:

```typescript
// @review-ok: parameterized query handled by ORM
const query = `SELECT * FROM users WHERE id = ${sanitizedId}`;
```

```python
# @review-ok: global cache intentional for performance
CACHE = {}
```

### Step 5: Report to improve the skill

If the same false positive keeps appearing across reviews:

1. Open issue at [github.com/your-org/claude-code-review-skill/issues](https://github.com/your-org/claude-code-review-skill/issues)
2. Include:
   - File and line number
   - What was flagged
   - Why it's a false positive
   - Code snippet if possible

This helps improve the skill for everyone.

---

## Default behavior

The skill is designed to minimize false positives out of the box:

- **Baseline filtering** — Only reports issues introduced in current PR/changes (via git blame)
- **Confidence threshold** — Only reports issues with ≥70% confidence
- **Skips linter territory** — Doesn't flag formatting, style issues that ESLint/Prettier catch
- **Skips pre-existing issues** — Won't complain about old code you didn't touch
- **Skips trivial changes** — Version bumps, whitespace, documentation-only changes
