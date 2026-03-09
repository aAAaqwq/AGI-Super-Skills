# Stack Customization

## Adaptation Table

| Command | Python | Rust | .NET | Go |
|---------|--------|------|------|----|
| **Build** | _(interpreted)_ | `cargo build` | `dotnet build` | `go build ./...` |
| **Test** | `pytest tests/ -q` | `cargo test -- --quiet` | `dotnet test --logger "console;verbosity=minimal"` | `go test ./... -v 2>&1 \| tail -20` |
| **Lint** | `ruff check src/ tests/` | `cargo clippy -- -D warnings` | `dotnet format --verify-no-changes` | `golangci-lint run` |
| **Format** | `ruff format src/ tests/` | `cargo fmt --check` | `dotnet format` | `gofmt -w .` |
| **Coverage** | `pytest --cov=src tests/` | `cargo tarpaulin` | `dotnet test --collect:"XPlat Code Coverage"` | `go test -coverprofile=c.out ./...` |
| **Developer prompt** | `developer/python.md` | `developer/rust.md` | `developer/dotnet.md` | `developer/go.md` |
| **Architect prompt** | `architect/python.md` | `architect/rust.md` | `architect/dotnet.md` | `architect/go.md` |

---

## Python Stack

### Requirements
- Python 3.11+
- `pytest` for tests
- `ruff` for linting and formatting

### Developer subagent commands

```bash
# Install dependencies
pip install -r requirements.txt  # or: uv pip install -r requirements.txt

# Run tests
python3 -m pytest tests/ -q 2>&1 | tail -20

# Run linter
python3 -m ruff check src/ tests/ 2>&1 | head -30

# Fix lint errors
python3 -m ruff check --fix src/ tests/
python3 -m ruff format src/ tests/
```

### Fix subagent lint loop

```bash
while ! python3 -m ruff check src/ tests/ --quiet; do
    python3 -m ruff check --fix src/ tests/
    python3 -m ruff format src/ tests/
done
```

### Prompt files needed

```
prompts/developer/python.md
prompts/architect/python.md
prompts/tester/autotests.md
prompts/reviewer/general.md
prompts/security/general.md
```

---

## Rust Stack

### Requirements
- Rust stable toolchain
- `cargo clippy` for linting
- `cargo fmt` for formatting

### Developer subagent commands

```bash
# Build check (faster than full build)
cargo check 2>&1 | grep "^error" | head -20

# Run tests (quiet mode)
cargo test -- --quiet 2>&1 | tail -15

# Run clippy
cargo clippy -- -D warnings 2>&1 | head -30

# Format check
cargo fmt --check
```

### Lint and format in fix subagent

```bash
# Fix formatting
cargo fmt

# Check clippy (manual fix required)
cargo clippy -- -D warnings 2>&1 | head -30
# Fix issues, then:
cargo clippy -- -D warnings  # must be clean before commit
```

### Important: Rust context economy

```bash
# Prefer cargo check over cargo build for diagnostics
cargo check 2>&1 | grep "^error\[" | head -40

# Test with quiet flag
cargo test -- --quiet 2>&1 | tail -15

# Only full build when checking binary output
cargo build --release 2>&1 | grep -E "^error" | head -20
```

### Prompt files needed

```
prompts/developer/rust.md
prompts/architect/rust.md
prompts/tester/autotests.md
prompts/reviewer/general.md
prompts/security/general.md
```

---

## .NET Stack

### Requirements
- .NET 8 SDK
- `dotnet format` for formatting

### Developer subagent commands

```bash
# Build
dotnet build 2>&1 | grep -E "error|warning" | head -30

# Run tests
dotnet test --logger "console;verbosity=minimal" 2>&1 | tail -20

# Format check
dotnet format --verify-no-changes 2>&1 | head -20

# Apply format
dotnet format
```

### Fix subagent lint

```bash
dotnet format
dotnet build 2>&1 | grep "^.*error" | head -20
# Fix errors manually
dotnet test --logger "console;verbosity=minimal" 2>&1 | tail -20
```

### Prompt files needed

```
prompts/developer/dotnet.md
prompts/architect/dotnet.md
prompts/tester/autotests.md
prompts/reviewer/general.md
prompts/security/general.md
```

---

## Go Stack

### Requirements
- Go 1.21+
- `golangci-lint` for linting

### Developer subagent commands

```bash
# Build check
go build ./... 2>&1 | head -20

# Run tests
go test ./... -v 2>&1 | tail -30

# Lint
golangci-lint run 2>&1 | head -30

# Format
gofmt -w .
```

### Fix subagent lint loop

```bash
gofmt -w .
go vet ./... 2>&1 | head -20
golangci-lint run 2>&1 | head -30
```

### Prompt files needed

```
prompts/developer/go.md
prompts/architect/go.md
prompts/tester/autotests.md
prompts/reviewer/general.md
prompts/security/general.md
```

---

## Multi-Language Projects

For projects with multiple languages (e.g., Python backend + TypeScript frontend):

1. Set `STACK` based on primary language in `AGENTS.md`
2. Add secondary linters in developer/fix subagent tasks explicitly:
   ```bash
   # Python backend
   python3 -m ruff check src/ tests/
   # TypeScript frontend
   cd frontend && npm run lint
   ```
3. Use `developer/python.md` prompt but add TS-specific notes in `AGENTS.md`

---

## Updating SKILL.md for Your Stack

In `SKILL.md`, find the test/lint commands in subagent tasks and replace:

```
# Python → Rust example:

# Developer subagent section:
# Before: python3 -m pytest tests/ -q
# After:  cargo test -- --quiet

# Before: python3 -m ruff check src/ tests/
# After:  cargo clippy -- -D warnings

# Push command:
# Before: git push https://user:$(gh auth token)@github.com/org/repo.git <branch>
# After:  (same, just update org/repo)
```

---

## Stack Detection from AGENTS.md

The skill reads `AGENTS.md` to determine stack. Your project's `AGENTS.md` should include:

```markdown
## Stack
- Language: Python 3.12
- Test runner: pytest
- Linter: ruff
- Framework: FastAPI
```

The developer subagent selects `prompts/developer/python.md` based on this.
