# Clawguard Agent Notes
# Scope: repository root

## Quick orientation
- Runtime: Node.js >= 18 (see package.json engines)
- Module system: CommonJS (require/module.exports)
- CLI entry: bin/clawguard.js -> src/cli.js
- Core scanner: src/scanner.js
- Rules: rules/rules.json, src/rules.js, src/rulepack.js
- Tests: tests/run.js (minimal assert-based test)

## Build, lint, test
There is no build step and no lint/format tooling configured.

### Install
- npm install
- npm link (optional for global CLI)

### Run the CLI locally
- node bin/clawguard.js --help
- node bin/clawguard.js scan --path ~/.openclaw

### Test suite
- npm test
  - runs: node tests/run.js

### Run a single test
- There is only one test file.
- Run it directly:
  - node tests/run.js

### Lint / format
- Not configured. Do not introduce new linters/formatters unless asked.

## Code style guidelines

### Language and modules
- Use CommonJS: const x = require("...") and module.exports = { ... }.
- Do not add TypeScript or ESM unless explicitly requested.

### Imports
- Keep require statements at the top of the file.
- Order: Node core modules first, then local modules.
- Prefer destructuring imports for local helpers:
  - const { scanPaths } = require("./scanner");

### Formatting
- Indentation: 2 spaces.
- Use double quotes for strings.
- Use semicolons.
- Keep line width reasonable; wrap long argument lists or template strings.
- Prefer trailing commas only when existing code uses them in that block.

### Naming
- Use camelCase for variables and functions.
- Use PascalCase for classes (rare in this repo).
- Use UPPER_SNAKE_CASE for constants:
  - DEFAULT_RULES_URL, MAX_FILE_SIZE_BYTES
- File names are lowercase with .js extension.

### Functions and structure
- Keep functions small and focused.
- Prefer pure helpers in src/utils.js when reusable across modules.
- Use explicit return objects rather than throwing for expected conditions.

### Error handling
- For file/network operations, wrap in try/catch and surface error.message.
- CLI paths should log actionable messages via console.error.
- Use process.exit(code) for CLI error status (see src/cli.js patterns).
- Avoid throwing across the CLI boundary unless the caller handles it.

### Logging
- Use console.log for normal output.
- Use console.error for warnings or failures.
- Keep log text user-facing and concise.

### Data handling
- JSON output uses JSON.stringify(value, null, 2).
- Avoid mutating function inputs; clone when needed.

### Security and safety
- Avoid executing external commands unless explicitly required.
- When using child_process, prefer spawn/spawnSync with explicit args.
- Do not pass user-provided input directly into shell commands.

## Tests and fixtures
- Tests use Node's built-in assert module.
- Add new fixtures under tests/fixtures if needed.
- Keep tests deterministic; avoid network or OS-specific dependencies.

## Project conventions by area

### CLI (src/cli.js)
- Parses args manually; mirror existing parsing patterns.
- Return non-zero exit codes for failures (1 for usage, 2 for blocked).
- For new commands, update printHelp() and parse functions.

### Scanner (src/scanner.js)
- Respect ignore patterns and DEFAULT_IGNORE_DIRS.
- Keep rule matching line-based using regex.
- Avoid reading huge files; MAX_FILE_SIZE_BYTES is 1 MB.

### Rule packs (src/rulepack.js)
- Validate schema before writing.
- Use fetchJson() with https and simple error handling.

### Reporting (src/report.js)
- Keep text report human-readable and concise.
- JSON output should remain stable for automation.

## External rules
- No Cursor rules found in .cursor/rules or .cursorrules.
- No Copilot instructions found in .github/copilot-instructions.md.

## When in doubt
- Follow patterns in existing files.
- Keep changes minimal and focused.
- Ask only when a decision would change behavior or compatibility.
