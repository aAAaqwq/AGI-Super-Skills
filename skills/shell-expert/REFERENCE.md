# Shell Expert - Detailed Reference

## Command-Line Tools Reference

### jq - JSON Query and Transformation

```bash
# Pretty-print JSON
jq . data.json

# Extract specific value
jq -r '.key.subkey' data.json

# Filter arrays
jq '.items[] | select(.status == "active")' data.json

# Transform structure
jq '{name: .fullName, age: .years}' data.json

# Multiple filters
jq '.items[] | select(.status == "active") | {name, id}' data.json

# Array operations
jq '[.items[] | .price] | add' data.json  # Sum prices
jq '.items | length' data.json            # Count items
jq '.items | sort_by(.name)' data.json    # Sort array
```

### yq - YAML Query and Edit

```bash
# Read value
yq '.services.web.image' docker-compose.yml

# Update in-place
yq -i '.version = "2.1.0"' config.yml

# Convert YAML to JSON
yq -o json config.yml

# Convert JSON to YAML
yq -P config.json

# Merge YAML files
yq eval-all 'select(fileIndex == 0) * select(fileIndex == 1)' base.yml override.yml

# Delete key
yq -i 'del(.obsolete.key)' config.yml

# Add array element
yq -i '.items += ["new-item"]' config.yml
```

### jd - JSON Diff and Patch

```bash
# Show differences
jd v1.json v2.json

# Create patch file
jd -set v1.json v2.json > patch.json

# Apply patch
jd -p patch.json v1.json

# Output formats
jd -f patch v1.json v2.json  # Patch format
jd -f merge v1.json v2.json  # Merge format
```

### fd - Modern Find Alternative

```bash
# Find by pattern
fd 'ReportGenerator'

# Find by extension
fd -e md
fd -e 'js' -e 'ts'  # Multiple extensions

# Find and execute
fd -e sh -x shellcheck {}

# Find with size constraints
fd --size +1M       # Larger than 1MB
fd --size -10k      # Smaller than 10KB

# Find by type
fd -t f             # Files only
fd -t d             # Directories only
fd -t l             # Symlinks only

# Exclude patterns
fd -E 'node_modules' -E '.git'

# Case-insensitive
fd -i readme
```

### rg (ripgrep) - Fast Recursive Grep

```bash
# Basic search
rg 'DATABASE_URL'

# Search specific file types
rg 'TODO' -t python
rg 'import' -t js -t ts

# Search with context
rg -C 3 'error'      # 3 lines before and after
rg -A 2 'error'      # 2 lines after
rg -B 2 'error'      # 2 lines before

# Search and replace preview
rg 'old_name' --replace 'new_name'

# Case-insensitive
rg -i 'error'

# Whole word match
rg -w 'test'

# Show files without matches
rg --files-without-match 'pattern'

# Count matches
rg -c 'pattern'

# Only show filenames
rg -l 'pattern'

# Ignore git and hidden files
rg --no-ignore --hidden 'pattern'
```

### lsd - Modern ls

```bash
# List with icons and details
lsd -l

# Tree view
lsd --tree
lsd --tree --depth 2

# Sort by time
lsd -lt

# Sort by size
lsd -lS

# Show file permissions octal
lsd -l --permission octal

# Human-readable sizes
lsd -lh

# Show all files including hidden
lsd -la
```

### mermaid-cli - Diagrams as Code

```bash
# Generate SVG from Mermaid definition
mmdc -i flow.mmd -o flow.svg

# Generate PNG with custom theme
mmdc -i diagram.mmd -o diagram.png -t dark

# Generate PDF
mmdc -i chart.mmd -o chart.pdf

# Set background color
mmdc -i diagram.mmd -o diagram.png -b transparent

# Set width
mmdc -i diagram.mmd -o diagram.png -w 1920
```

## Advanced Automation Examples

### Parallel Execution Pattern

```bash
# Using GNU parallel
find . -name "*.log" | parallel -j+0 gzip {}

# Using xargs
find . -name "*.txt" -print0 | xargs -0 -P 4 -I {} process_file {}

# Background jobs with wait
for file in *.data; do
    process_heavy "$file" &
    # Limit concurrent jobs
    while (( $(jobs -r | wc -l) >= 4 )); do
        sleep 0.1
    done
done
wait # Wait for all remaining jobs

# Parallel with progress
parallel --bar -j4 process_file ::: *.txt
```

### Cross-Platform Detection

```bash
detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        DISTRO="$ID"
        DISTRO_VERSION="$VERSION_ID"
    fi
}

detect_architecture() {
    case "$(uname -m)" in
        x86_64)  ARCH="amd64" ;;
        aarch64) ARCH="arm64" ;;
        armv7l)  ARCH="armv7" ;;
        *)       ARCH="unknown" ;;
    esac
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}
```

### Argument Parsing

```bash
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--verbose)
                VERBOSE=1
                shift
                ;;
            -o|--output)
                OUTPUT_FILE="$2"
                shift 2
                ;;
            --)
                shift
                break
                ;;
            -*)
                echo "Unknown option: $1" >&2
                exit 1
                ;;
            *)
                POSITIONAL_ARGS+=("$1")
                shift
                ;;
        esac
    done
}
```

### File Locking

```bash
# Using flock
(
    flock -x 200  # Exclusive lock
    # Critical section
    echo "Processing..."
) 200>/var/lock/myapp.lock

# Using mkdir (atomic operation)
lock_dir="/var/lock/myapp.lock"
if mkdir "$lock_dir" 2>/dev/null; then
    trap 'rmdir "$lock_dir"' EXIT
    # Critical section
else
    echo "Another instance is running" >&2
    exit 1
fi
```

### Retry Logic

```bash
retry() {
    local max_attempts="$1"
    local delay="$2"
    local command="${@:3}"
    local attempt=1

    until $command; do
        if (( attempt >= max_attempts )); then
            echo "Command failed after $max_attempts attempts" >&2
            return 1
        fi
        echo "Attempt $attempt failed. Retrying in ${delay}s..." >&2
        sleep "$delay"
        ((attempt++))
    done
}

# Usage
retry 3 5 curl -f https://example.com/api
```

### Logging Functions

```bash
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >&2
}

log_info() {
    log "INFO: $*"
}

log_error() {
    log "ERROR: $*"
}

log_debug() {
    [[ -n "${DEBUG:-}" ]] && log "DEBUG: $*"
}
```

### Configuration File Parsing

```bash
# Parse simple KEY=VALUE config
parse_config() {
    local config_file="$1"
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue

        # Remove leading/trailing whitespace
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)

        # Export as environment variable
        export "$key"="$value"
    done < "$config_file"
}
```

## Troubleshooting Guide

### Common Issues and Solutions

**Spaces in filenames**
```bash
# Wrong
for file in $(find . -name "*.txt"); do
    process "$file"  # Breaks on spaces
done

# Right
find . -name "*.txt" -print0 | while IFS= read -r -d '' file; do
    process "$file"
done

# Or use array
while IFS= read -r -d '' file; do
    files+=("$file")
done < <(find . -name "*.txt" -print0)

for file in "${files[@]}"; do
    process "$file"
done
```

**Pipe failures**
```bash
# Without pipefail
false | true
echo $?  # Returns 0

# With pipefail
set -o pipefail
false | true
echo $?  # Returns 1
```

**Race conditions**
```bash
# Wrong - race condition
if [[ ! -f "$file" ]]; then
    touch "$file"
fi

# Right - atomic operation
set -o noclobber
echo "data" > "$file" || {
    echo "File already exists" >&2
    exit 1
}
```

**Signal handling**
```bash
cleanup() {
    local exit_code=$?
    # Cleanup resources
    rm -f "$TEMP_FILE"
    kill "${CHILD_PID:-}" 2>/dev/null
    exit $exit_code
}

trap cleanup EXIT
trap 'echo "Interrupted" >&2; exit 130' INT
trap 'echo "Terminated" >&2; exit 143' TERM
```

**Performance issues**
```bash
# Wrong - slow
for file in *.log; do
    count=$(grep -c "ERROR" "$file")
    echo "$file: $count"
done

# Right - faster
grep -c "ERROR" *.log

# Profile with time
time {
    # Commands to profile
}

# Profile with strace
strace -c script.sh
```

**Portability problems**
```bash
# Test POSIX compliance
dash script.sh
ash script.sh

# Check for bash-specific features
shellcheck --shell=sh script.sh

# Portable shebang
#!/usr/bin/env bash

# Check for required commands
for cmd in jq curl; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: $cmd is required but not installed" >&2
        exit 1
    fi
done
```

## Performance Optimization Tips

1. **Avoid unnecessary subshells**: Use `${var//search/replace}` instead of `$(echo "$var" | sed 's/search/replace/')`
2. **Use built-in commands**: Prefer `[[ ]]` over `[ ]`, use `${#var}` instead of `$(echo "$var" | wc -c)`
3. **Minimize external commands**: Use bash built-ins when possible
4. **Batch operations**: Process multiple files at once instead of one by one
5. **Use parallel processing**: Leverage multiple cores with parallel or xargs -P
6. **Profile before optimizing**: Use `time` and `strace` to identify bottlenecks
