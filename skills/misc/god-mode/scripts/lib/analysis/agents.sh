#!/usr/bin/env bash
# Agent file detection and analysis for god-mode
# Finds and reads agent instruction files (agents.md, CLAUDE.md, etc.)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config.sh"
source "$SCRIPT_DIR/../db.sh"

# Default agent file patterns (in search order)
DEFAULT_AGENT_FILES=(
    "agents.md"
    "AGENTS.md"
    "CLAUDE.md"
    ".claude/CLAUDE.md"
    ".github/copilot-instructions.md"
    ".cursorrules"
    ".cursor/rules"
    "CODEX.md"
    "GEMINI.md"
    ".windsurfrules"
)

# Find agent file in a local directory
# Usage: find_agent_file "/path/to/repo"
# Returns: path to first matching agent file, or empty
find_agent_file() {
    local repo_path="$1"

    # Expand ~ in path
    repo_path="${repo_path/#\~/$HOME}"

    if [[ ! -d "$repo_path" ]]; then
        return 1
    fi

    # Get configured patterns or use defaults
    local patterns
    if config_exists; then
        mapfile -t patterns < <(config_get_agent_files)
    else
        patterns=("${DEFAULT_AGENT_FILES[@]}")
    fi

    # Search for files in order
    for pattern in "${patterns[@]}"; do
        local file_path="$repo_path/$pattern"
        if [[ -f "$file_path" ]]; then
            echo "$file_path"
            return 0
        fi
    done

    return 1
}

# Find agent file via GitHub API (for repos without local clone)
# Usage: find_agent_file_remote "user/repo"
# Returns: JSON { path: string, content: string } or null
find_agent_file_remote() {
    local repo="$1"

    if ! command -v gh &>/dev/null; then
        echo "null"
        return 1
    fi

    # Get configured patterns or use defaults
    local patterns
    if config_exists; then
        mapfile -t patterns < <(config_get_agent_files)
    else
        patterns=("${DEFAULT_AGENT_FILES[@]}")
    fi

    # Try each pattern
    for pattern in "${patterns[@]}"; do
        local content
        content=$(gh api "repos/$repo/contents/$pattern" --jq '.content' 2>/dev/null)

        if [[ -n "$content" && "$content" != "null" ]]; then
            # Decode base64 content
            local decoded
            decoded=$(echo "$content" | base64 -d 2>/dev/null || echo "")

            if [[ -n "$decoded" ]]; then
                jq -n --arg path "$pattern" --arg content "$decoded" \
                    '{path: $path, content: $content}'
                return 0
            fi
        fi
    done

    echo "null"
    return 1
}

# Get agent file content for a project
# Usage: get_agent_content "github:user/repo"
# Returns: JSON { path: string, content: string, source: "local"|"remote" } or null
get_agent_content() {
    local project_id="$1"

    # Get project config
    local project=$(config_get_project "$project_id")
    if [[ -z "$project" || "$project" == "null" ]]; then
        echo "null"
        return 1
    fi

    local local_path=$(echo "$project" | jq -r '.local // ""')
    local provider=$(config_parse_provider "$project_id")
    local repo=$(config_parse_repo "$project_id")

    # Try local first
    if [[ -n "$local_path" ]]; then
        local_path="${local_path/#\~/$HOME}"
        local agent_file
        agent_file=$(find_agent_file "$local_path")

        if [[ -n "$agent_file" ]]; then
            local content
            content=$(cat "$agent_file")
            local rel_path="${agent_file#$local_path/}"

            jq -n --arg path "$rel_path" --arg content "$content" --arg source "local" \
                '{path: $path, content: $content, source: $source}'
            return 0
        fi
    fi

    # Fall back to remote (GitHub only)
    if [[ "$provider" == "github" ]]; then
        local result
        result=$(find_agent_file_remote "$repo")

        if [[ "$result" != "null" ]]; then
            echo "$result" | jq '. + {source: "remote"}'
            return 0
        fi
    fi

    echo "null"
    return 1
}

# Calculate hash of agent file content (for cache invalidation)
# Usage: hash_agent_content "content string"
hash_agent_content() {
    local content="$1"

    if command -v md5sum &>/dev/null; then
        echo "$content" | md5sum | cut -d' ' -f1
    elif command -v md5 &>/dev/null; then
        echo "$content" | md5
    else
        # Fallback: use content length as rough hash
        echo "len_${#content}"
    fi
}

# Parse sections from agent file
# Usage: parse_agent_sections "content"
# Returns: JSON array of { heading: string, content: string }
parse_agent_sections() {
    local content="$1"

    # Parse markdown headings and their content
    local result="[]"
    local current_heading=""
    local current_content=""

    while IFS= read -r line; do
        if [[ "$line" =~ ^##?[[:space:]](.+)$ ]]; then
            # Save previous section
            if [[ -n "$current_heading" ]]; then
                result=$(echo "$result" | jq --arg h "$current_heading" --arg c "$current_content" \
                    '. += [{heading: $h, content: ($c | gsub("^\\s+|\\s+$"; ""))}]')
            fi
            current_heading="${BASH_REMATCH[1]}"
            current_content=""
        else
            current_content+="$line"$'\n'
        fi
    done <<< "$content"

    # Save last section
    if [[ -n "$current_heading" ]]; then
        result=$(echo "$result" | jq --arg h "$current_heading" --arg c "$current_content" \
            '. += [{heading: $h, content: ($c | gsub("^\\s+|\\s+$"; ""))}]')
    fi

    echo "$result"
}

# Extract key topics mentioned in agent file
# Usage: extract_agent_topics "content"
# Returns: JSON array of topics found
extract_agent_topics() {
    local content="$1"
    local content_lower=$(echo "$content" | tr '[:upper:]' '[:lower:]')

    local topics=(
        "testing" "tests" "test"
        "error handling" "errors" "exceptions"
        "documentation" "docs" "comments"
        "security" "authentication" "auth"
        "performance" "optimization" "caching"
        "code style" "formatting" "lint"
        "typescript" "javascript" "python" "rust" "go"
        "react" "vue" "angular"
        "api" "rest" "graphql"
        "database" "sql" "orm"
        "git" "commits" "branches"
        "ci/cd" "deployment" "docker"
    )

    local found="[]"
    for topic in "${topics[@]}"; do
        if [[ "$content_lower" == *"$topic"* ]]; then
            found=$(echo "$found" | jq --arg t "$topic" '. += [$t]')
        fi
    done

    echo "$found" | jq 'unique'
}

# Store agent file snapshot in database (for tracking changes)
# Usage: store_agent_snapshot "github:user/repo" "path" "content"
store_agent_snapshot() {
    local project_id="$1"
    local path="$2"
    local content="$3"

    local hash=$(hash_agent_content "$content")
    local now=$(date +%s)

    # Escape content for SQL
    local escaped_content=$(echo "$content" | sed "s/'/''/g")

    db_exec "INSERT INTO agent_files (project_id, path, content_hash, content, captured_at)
             VALUES ('$project_id', '$path', '$hash', '$escaped_content', $now)
             ON CONFLICT(project_id, path) DO UPDATE SET
                 content_hash = '$hash',
                 content = '$escaped_content',
                 captured_at = $now;"

    echo "$hash"
}

# Get previous agent file snapshot
# Usage: get_agent_snapshot "github:user/repo"
# Returns: JSON { path, content_hash, content, captured_at } or null
get_agent_snapshot() {
    local project_id="$1"

    db_query "SELECT * FROM agent_files
              WHERE project_id = '$project_id'
              ORDER BY captured_at DESC
              LIMIT 1" | jq '.[0] // null'
}

# Check if agent file has changed since last snapshot
# Usage: agent_file_changed "github:user/repo" "current_content"
# Returns: 0 if changed, 1 if same
agent_file_changed() {
    local project_id="$1"
    local current_content="$2"

    local current_hash=$(hash_agent_content "$current_content")
    local snapshot=$(get_agent_snapshot "$project_id")

    if [[ "$snapshot" == "null" ]]; then
        return 0  # No snapshot = consider changed
    fi

    local stored_hash=$(echo "$snapshot" | jq -r '.content_hash')

    [[ "$current_hash" != "$stored_hash" ]]
}
