# Example: Rust Project (ralph-rs)

Real-world example from the `ralph-rs` project — a Rust CLI tool.

## Project Context

- **Stack:** Rust stable, cargo, clippy
- **Task:** Implement config file support
- **Branch:** `feat/config-file`

---

## Key Differences from Python

### Test command

```bash
# Python:
python3 -m pytest tests/ -q 2>&1 | tail -20

# Rust:
cargo test -- --quiet 2>&1 | tail -15
```

### Lint command

```bash
# Python:
python3 -m ruff check src/ tests/

# Rust:
cargo clippy -- -D warnings 2>&1 | head -30
```

### Build check (prefer over full build for context economy)

```bash
# Use cargo check for faster error detection:
cargo check 2>&1 | grep "^error" | head -20

# Full build only when needed:
cargo build 2>&1 | grep -E "^error\[|^error:" | head -20
```

---

## Developer Subagent — Task Prompt (Rust)

```
## DEVELOPER SUBAGENT — ralph-rs implement config file support

INIT:
- cd /opt/projects/ralph-rs
- git fetch origin && git pull origin main
- git checkout -b feat/config-file
- Read AGENTS.md (Critical Rules, Stack, Structure)
- Read src/ to understand current architecture

DEVELOP:
- Read prompts/developer/rust.md
- Implement config file parsing (TOML format, using `toml` crate)
- Config file location: ~/.config/ralph/config.toml
- Fallback to defaults if file not found
- Use serde for deserialization

TEST:
- Read prompts/tester/autotests.md
- Write tests for:
  * Config file loading (happy path)
  * Missing config file (fallback to defaults)
  * Invalid TOML (error handling)
  * Config value overrides
- Run: cargo test -- --quiet 2>&1 | tail -15
- All tests must pass

LINT:
- cargo clippy -- -D warnings 2>&1 | head -30
- Fix all clippy warnings before commit
- cargo fmt --check (apply cargo fmt if needed)
- Must be clean before commit

DOCS:
- Update AGENTS.md: add Config struct to Stack section
- Update README.md: add config file section with example TOML
- Update AGENTS.md Status: mark config file feature as implemented

git add -A
git commit -m "feat: add config file support (TOML, ~/.config/ralph/config.toml)"
git push https://KoshelevDV:$(gh auth token)@github.com/KoshelevDV/ralph-rs.git feat/config-file

Output:
BRANCH: feat/config-file
STACK: rust
TESTS: 18 passed
LINT: clippy clean
DOCS: AGENTS.md updated, README.md updated
DIFF_SUMMARY: Added Config struct with serde, load_config() function, TOML parsing via toml crate, 4 new tests covering happy path + error cases
```

---

## Architect Review — Rust-Specific Focus

```
## ARCHITECT REVIEW — Rust

Key architectural concerns for Rust projects:

### Ownership and lifetimes
- Does the new code introduce unnecessary clones?
- Are lifetimes explicit where needed?
- Does config data outlive the parsers?

### Error handling
- Is `?` operator used consistently?
- Are errors typed with `thiserror` / `anyhow`?
- Are errors propagated, not swallowed?

### API design
- Is Config struct `pub` only where needed?
- Is the config loading function testable (dependency injection)?
- Does it use `PathBuf` not `String` for paths?

### Dependencies
- Is `toml` the right choice vs `serde_json` or `config` crate?
- Are new crate versions pinned appropriately?

DIFF review scope: ONLY changes in this PR.
```

---

## Example Clippy Findings (BLOCKING)

Developer subagent output before fix:

```
cargo clippy -- -D warnings

error: redundant clone
  --> src/config.rs:45:30
   |
45 |     let path = config_path.clone().to_str()...
   |
   = help: remove `.clone()`
   [clippy::redundant_clone]

error: use of `unwrap` in a function that returns `Result`
  --> src/config.rs:67:18
   |  
67 |     let content = fs::read_to_string(&path).unwrap();
   |
   = help: use `?` instead
   [clippy::unwrap_used]

error[E0499]: cannot borrow `config` as mutable more than once at a time
  --> src/config.rs:89:5
```

After fix:
```
cargo clippy -- -D warnings
    Finished dev [unoptimized + debuginfo] target(s) in 2.34s
(no output = clean)
```

---

## Context Economy Tips for Rust

```bash
# BAD (full build, lots of output):
cargo build

# GOOD (errors only):
cargo check 2>&1 | grep "^error" | head -20

# BAD (verbose test output):
cargo test

# GOOD (quiet, just results):
cargo test -- --quiet 2>&1 | tail -15

# BAD (full clippy with lots of warnings):
cargo clippy

# GOOD (only errors, fail on warnings):
cargo clippy -- -D warnings 2>&1 | head -30

# Redirect large outputs to file:
cargo build 2>&1 > /tmp/build.log && grep "^error" /tmp/build.log | head -20
```

---

## Cycle Output (Rust Project)

```
✅ Full cycle завершён — ralph-rs / feat/config-file

Tests:   18 passed / 18 total
Commits: 3

Self-review:
  Developer  — 2 blocking fixed (redundant clone, unwrap→?), 1 minor → issue
  Architect  — 1 blocking fixed (Config not Send+Sync), 0 minor
  QA/Manual  — 4 ACs covered (load/fallback/invalid/override)
  Security   — CLEAR (config paths sanitized, no secrets in config)
  Final      — APPROVE ✅

PR: https://github.com/KoshelevDV/ralph-rs/pull/7
Issues: https://github.com/KoshelevDV/ralph-rs/issues/8
```

**Fix subagent was needed** (blocking = 3):
- Round 1: fix clippy errors + ownership issue → 1 round sufficient
- Re-review after fix: 0 blocking → PR created

---

## Lessons Learned (Rust-specific)

```markdown
## Pitfalls

- **clippy::unwrap_used in Result context**: Always use `?` operator 
  in functions returning Result. clippy -D warnings catches this.
  
- **Config struct thread-safety**: If Config is shared across async 
  tasks, it must implement Send + Sync. Use Arc<RwLock<Config>> for 
  mutable shared config.
  
- **toml crate vs config crate**: `toml` is simpler for single-file 
  configs. `config` crate supports multi-source merging (file + env vars).
  For ralph-rs, `toml` was sufficient.
  
- **cargo check vs cargo build**: Always use cargo check for error 
  detection in subagents — it's 3-5x faster and produces the same 
  error messages without building binaries.
```
