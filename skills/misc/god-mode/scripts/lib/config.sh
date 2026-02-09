#!/usr/bin/env bash
# Configuration loading for god-mode
# Parses YAML config from ~/.config/god-mode/config.yaml

GOD_MODE_CONFIG="${GOD_MODE_CONFIG:-$HOME/.config/god-mode/config.yaml}"
GOD_MODE_HOME="${GOD_MODE_HOME:-$HOME/.god-mode}"

# Check if yq is available (preferred YAML parser)
_has_yq() {
    command -v yq &>/dev/null
}

# Initialize config (create default if missing)
config_init() {
    local config_dir
    config_dir="$(dirname "$GOD_MODE_CONFIG")"

    if [[ ! -d "$config_dir" ]]; then
        mkdir -p "$config_dir"
    fi

    if [[ ! -f "$GOD_MODE_CONFIG" ]]; then
        cat > "$GOD_MODE_CONFIG" << 'EOF'
# god-mode configuration

projects: []

sync:
  initialDays: 90
  commitsCacheMinutes: 60
  prsCacheMinutes: 15
  issuesCacheMinutes: 15

analysis:
  agentFiles:
    - agents.md
    - AGENTS.md
    - CLAUDE.md
    - .github/copilot-instructions.md
    - .cursorrules
  analysisWindowDays: 90

output:
  colors: true
  defaultDetail: normal
  localTime: true
EOF
        echo "Created default config at $GOD_MODE_CONFIG"
    fi
}

# Check if config file exists
config_exists() {
    [[ -f "$GOD_MODE_CONFIG" ]]
}

# Get a config value using yq or fallback grep
# Usage: config_get "sync.initialDays" "90"
config_get() {
    local path="$1"
    local default="${2:-}"

    if ! config_exists; then
        echo "$default"
        return
    fi

    if _has_yq; then
        local value
        value=$(yq -r ".$path // \"\"" "$GOD_MODE_CONFIG" 2>/dev/null)
        if [[ -n "$value" && "$value" != "null" ]]; then
            echo "$value"
        else
            echo "$default"
        fi
    else
        # Fallback: simple grep for top-level scalar values
        # Only works for simple cases like "initialDays: 90"
        local key="${path##*.}"
        local value
        value=$(grep -E "^\s*${key}:" "$GOD_MODE_CONFIG" 2>/dev/null | head -1 | sed 's/.*:\s*//' | tr -d '"')
        if [[ -n "$value" ]]; then
            echo "$value"
        else
            echo "$default"
        fi
    fi
}

# Get all projects as JSON array
# Returns: [{"id": "github:user/repo", "name": "...", "priority": "...", ...}, ...]
config_get_projects() {
    if ! config_exists; then
        echo "[]"
        return
    fi

    if _has_yq; then
        yq -o=json '.projects // []' "$GOD_MODE_CONFIG" 2>/dev/null || echo "[]"
    else
        # Fallback: parse projects manually (limited support)
        _parse_projects_fallback
    fi
}

# Get a single project by ID or name
# Usage: config_get_project "myproject"
config_get_project() {
    local search="$1"
    local projects
    projects=$(config_get_projects)

    # Search by exact ID first, then by name substring
    echo "$projects" | jq -c --arg s "$search" '
        (.[] | select(.id == $s)) //
        (.[] | select(.name != null and (.name | ascii_downcase | contains($s | ascii_downcase)))) //
        (.[] | select(.id | ascii_downcase | contains($s | ascii_downcase))) //
        null
    ' 2>/dev/null | head -1
}

# Get project count
config_project_count() {
    config_get_projects | jq 'length'
}

# Get sync settings as JSON
config_get_sync() {
    if ! config_exists; then
        echo '{"initialDays": 90, "commitsCacheMinutes": 60, "prsCacheMinutes": 15, "issuesCacheMinutes": 15}'
        return
    fi

    if _has_yq; then
        yq -o=json '.sync // {}' "$GOD_MODE_CONFIG" 2>/dev/null || echo '{}'
    else
        # Return defaults
        echo '{"initialDays": 90, "commitsCacheMinutes": 60, "prsCacheMinutes": 15, "issuesCacheMinutes": 15}'
    fi
}

# Get analysis settings as JSON
config_get_analysis() {
    if ! config_exists; then
        echo '{"agentFiles": ["agents.md", "AGENTS.md", "CLAUDE.md"], "analysisWindowDays": 90}'
        return
    fi

    if _has_yq; then
        yq -o=json '.analysis // {}' "$GOD_MODE_CONFIG" 2>/dev/null || echo '{}'
    else
        echo '{"agentFiles": ["agents.md", "AGENTS.md", "CLAUDE.md"], "analysisWindowDays": 90}'
    fi
}

# Get agent file patterns as newline-separated list
config_get_agent_files() {
    if _has_yq && config_exists; then
        yq -r '.analysis.agentFiles // ["agents.md", "AGENTS.md", "CLAUDE.md"] | .[]' "$GOD_MODE_CONFIG" 2>/dev/null
    else
        echo "agents.md"
        echo "AGENTS.md"
        echo "CLAUDE.md"
        echo ".github/copilot-instructions.md"
        echo ".cursorrules"
    fi
}

# Get output settings
config_get_output() {
    if ! config_exists; then
        echo '{"colors": true, "defaultDetail": "normal", "localTime": true}'
        return
    fi

    if _has_yq; then
        yq -o=json '.output // {}' "$GOD_MODE_CONFIG" 2>/dev/null || echo '{}'
    else
        echo '{"colors": true, "defaultDetail": "normal", "localTime": true}'
    fi
}

# Check if colors are enabled
config_colors_enabled() {
    local colors
    colors=$(config_get "output.colors" "true")
    [[ "$colors" == "true" ]]
}

# Add a project to config
# Usage: config_add_project "github:user/repo" "My Project" "high"
config_add_project() {
    local id="$1"
    local name="${2:-}"
    local priority="${3:-medium}"

    if ! config_exists; then
        config_init
    fi

    if ! _has_yq; then
        echo "Error: yq is required to modify config" >&2
        echo "Install with: brew install yq (macOS) or apt install yq (Debian/Ubuntu)" >&2
        return 1
    fi

    # Check if project already exists
    local existing
    existing=$(config_get_project "$id")
    if [[ -n "$existing" && "$existing" != "null" ]]; then
        echo "Project already exists: $id" >&2
        return 1
    fi

    # Build new project entry
    local new_project="{\"id\": \"$id\""
    [[ -n "$name" ]] && new_project="$new_project, \"name\": \"$name\""
    new_project="$new_project, \"priority\": \"$priority\"}"

    # Add to config
    yq -i ".projects += [$new_project]" "$GOD_MODE_CONFIG"
    echo "Added project: $id"
}

# Remove a project from config
# Usage: config_remove_project "myproject"
config_remove_project() {
    local search="$1"

    if ! _has_yq; then
        echo "Error: yq is required to modify config" >&2
        return 1
    fi

    # Find the project first
    local project
    project=$(config_get_project "$search")
    if [[ -z "$project" || "$project" == "null" ]]; then
        echo "Project not found: $search" >&2
        return 1
    fi

    local id
    id=$(echo "$project" | jq -r '.id')

    # Remove from config
    yq -i "del(.projects[] | select(.id == \"$id\"))" "$GOD_MODE_CONFIG"
    echo "Removed project: $id"
}

# Parse provider from project ID
# Usage: config_parse_provider "github:user/repo" -> "github"
config_parse_provider() {
    local id="$1"
    echo "${id%%:*}"
}

# Parse repo path from project ID
# Usage: config_parse_repo "github:user/repo" -> "user/repo"
config_parse_repo() {
    local id="$1"
    echo "${id#*:}"
}

# Fallback parser for projects (when yq is not available)
# Limited support - only extracts id field
_parse_projects_fallback() {
    if [[ ! -f "$GOD_MODE_CONFIG" ]]; then
        echo "[]"
        return
    fi

    local in_projects=false
    local projects="["
    local first=true

    while IFS= read -r line; do
        # Detect projects section
        if [[ "$line" =~ ^projects: ]]; then
            in_projects=true
            continue
        fi

        # Exit projects section on new top-level key
        if [[ "$in_projects" == true && "$line" =~ ^[a-z]+: && ! "$line" =~ ^[[:space:]] ]]; then
            in_projects=false
            continue
        fi

        # Extract project ID
        if [[ "$in_projects" == true && "$line" =~ ^[[:space:]]+-[[:space:]]*id:[[:space:]]*(.+) ]]; then
            local id="${BASH_REMATCH[1]}"
            id=$(echo "$id" | tr -d '"' | tr -d "'")
            [[ "$first" == false ]] && projects="$projects,"
            projects="$projects{\"id\":\"$id\"}"
            first=false
        fi
    done < "$GOD_MODE_CONFIG"

    projects="$projects]"
    echo "$projects"
}
