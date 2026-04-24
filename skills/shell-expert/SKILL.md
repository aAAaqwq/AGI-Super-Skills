---
created: 2025-12-16
modified: 2025-12-16
reviewed: 2026-02-08
name: shell-expert
description: |
  Shell scripting expertise, command-line tools, automation, and cross-platform
  scripting best practices. Covers shell script development, CLI tool usage,
  and system automation with bash, zsh, and POSIX shell.
  Use when user mentions shell scripts, bash, zsh, CLI commands, pipes, command-line
  automation, or writing portable shell code.
user-invocable: false
allowed-tools: Bash, BashOutput, KillShell, Grep, Glob, Read, Write, Edit, TodoWrite
---

# Shell Expert

Expert knowledge for shell scripting, command-line tools, and automation with focus on robust, portable, and efficient solutions.

## Core Expertise

**Command-Line Tool Mastery**
- Expert knowledge of modern CLI tools (jq, yq, fd, rg, etc.)
- JSON/YAML processing and transformation
- File searching and text manipulation
- System automation and orchestration

**Shell Scripting Excellence**
- POSIX-compliant shell scripting for maximum portability
- Bash-specific features and best practices
- Error handling and defensive programming
- Cross-platform compatibility (Linux, macOS, BSD)

**Automation & Integration**
- CI/CD pipeline scripting
- System administration automation
- Tool integration and workflow automation
- Performance optimization for shell operations

## Key Capabilities

**JSON/YAML Processing**
- **jq**: Complex JSON queries, transformations, and filtering
- **yq**: YAML manipulation, in-place editing, format conversion
- **jd**: JSON diffing and patching for configuration management
- **Data pipeline construction**: Chaining tools for complex transformations

**File Operations & Search**
- **fd**: Fast, user-friendly file finding with intuitive syntax
- **rg (ripgrep)**: Lightning-fast recursive grep with gitignore support
- **lsd**: Modern ls replacement with visual enhancements
- **find/grep alternatives**: When and how to use modern replacements

**Shell Script Development**
- **Error Handling**: Proper trap usage, exit codes, error propagation
- **Input Validation**: Argument parsing, option handling, user input sanitization
- **Debugging**: Set options (-x, -e, -u, -o pipefail), debug output strategies
- **Performance**: Process substitution, parallel execution, efficient loops

**Cross-Platform Scripting**
- **Platform Detection**: OS-specific behavior handling
- **Path Management**: Portable path construction and manipulation
- **Tool Availability**: Checking for and handling missing dependencies
- **Compatibility Layers**: Writing scripts that work everywhere

**Automation Patterns**
- **Idempotent Operations**: Scripts that can run multiple times safely
- **Atomic Operations**: Ensuring all-or-nothing execution
- **Progress Reporting**: User-friendly output and status updates
- **Logging & Monitoring**: Structured logging for automated systems

## Essential Commands

**jq - JSON Processing**
```bash
jq . data.json                                    # Pretty-print
jq -r '.key.subkey' data.json                     # Extract value
jq '.items[] | select(.status == "active")'       # Filter
```

**yq - YAML Processing**
```bash
yq '.services.web.image' docker-compose.yml       # Read value
yq -i '.version = "2.1.0"' config.yml            # Update in-place
yq -o json config.yml                             # Convert to JSON
```

**fd - Fast File Finding**
```bash
fd 'pattern'                 # Find by pattern
fd -e md                     # Find by extension
fd -e sh -x shellcheck {}    # Find and execute
```

**rg - Recursive Grep**
```bash
rg 'DATABASE_URL'            # Basic search
rg 'TODO' -t python          # Search specific file types
rg -C 3 'error'              # Search with context
```

## Best Practices

**Script Development Workflow**
1. **Requirements Analysis**: Understand automation need and target platforms
2. **Tool Selection**: Choose appropriate tools for the task
3. **Prototype Development**: Create initial script with core functionality
4. **Error Handling**: Add robust error handling and edge case management
5. **Cross-Platform Testing**: Verify script works on all target systems
6. **Performance Optimization**: Profile and optimize for efficiency
7. **Documentation**: Add clear usage instructions and inline comments

**Critical Guidelines**
- Always use shellcheck for linting
- Set strict mode: `set -euo pipefail`
- Quote all variables: `"${var}"`
- Use functions for reusable code
- Implement proper cleanup with trap
- Provide helpful error messages
- Include --help and --version options
- Use meaningful variable names
- Comment complex logic
- Test with different shells when targeting POSIX

## Common Patterns

**Robust Script Template**
```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

trap 'echo "Error on line $LINENO"' ERR
trap cleanup EXIT

cleanup() {
    rm -f "$TEMP_FILE" 2>/dev/null || true
}

main() {
    parse_args "$@"
    validate_environment
    execute_task
}

main "$@"
```

**Cross-Platform Detection**
```bash
detect_os() {
    case "$OSTYPE" in
        linux*)   OS="linux" ;;
        darwin*)  OS="macos" ;;
        msys*)    OS="windows" ;;
        *)        OS="unknown" ;;
    esac
}
```

For detailed command-line tools reference, advanced automation examples, and troubleshooting guidance, see REFERENCE.md.
