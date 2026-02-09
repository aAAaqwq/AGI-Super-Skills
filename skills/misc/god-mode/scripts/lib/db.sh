#!/usr/bin/env bash
# Database operations for god-mode
# Uses SQLite stored at ~/.god-mode/cache.db

GOD_MODE_HOME="${GOD_MODE_HOME:-$HOME/.god-mode}"
DB_PATH="$GOD_MODE_HOME/cache.db"
SCHEMA_PATH="$(dirname "${BASH_SOURCE[0]}")/../../sql/schema.sql"

# Initialize database (create if not exists, run migrations)
db_init() {
    mkdir -p "$GOD_MODE_HOME"
    
    if [[ ! -f "$DB_PATH" ]]; then
        sqlite3 "$DB_PATH" < "$SCHEMA_PATH"
        echo "Database initialized at $DB_PATH"
    fi
}

# Run a query and return results as JSON
# Usage: db_query "SELECT * FROM projects"
db_query() {
    local sql="$1"
    sqlite3 -json "$DB_PATH" "$sql" 2>/dev/null || echo "[]"
}

# Run a query that doesn't return data
# Usage: db_exec "INSERT INTO ..."
db_exec() {
    local sql="$1"
    sqlite3 "$DB_PATH" "$sql"
}

# Upsert a project
# Usage: db_upsert_project "github:user/repo" "github" "My Project" "high"
db_upsert_project() {
    local id="$1"
    local provider="$2"
    local name="${3:-}"
    local priority="${4:-medium}"
    local tags="${5:-[]}"
    local local_path="${6:-}"
    
    db_exec "INSERT INTO projects (id, provider, name, priority, tags, local_path)
             VALUES ('$id', '$provider', '$name', '$priority', '$tags', '$local_path')
             ON CONFLICT(id) DO UPDATE SET
                 name = COALESCE(NULLIF('$name', ''), name),
                 priority = '$priority',
                 tags = '$tags',
                 local_path = COALESCE(NULLIF('$local_path', ''), local_path);"
}

# Upsert commits (batch)
# Usage: echo "$commits_json" | db_upsert_commits "github:user/repo"
db_upsert_commits() {
    local project_id="$1"
    local commits
    commits=$(cat)
    
    # Parse JSON and insert each commit
    echo "$commits" | jq -c '.[]' | while read -r commit; do
        local sha=$(echo "$commit" | jq -r '.sha')
        local author=$(echo "$commit" | jq -r '.author // .commit.author.name')
        local message=$(echo "$commit" | jq -r '.message // .commit.message' | head -1 | sed "s/'/''/g")
        local timestamp=$(echo "$commit" | jq -r '.date // .commit.author.date')
        
        # Convert ISO date to Unix timestamp if needed
        if [[ "$timestamp" =~ ^[0-9]{4}- ]]; then
            timestamp=$(date -d "$timestamp" +%s 2>/dev/null || echo "0")
        fi
        
        db_exec "INSERT OR REPLACE INTO commits (sha, project_id, author, message, timestamp)
                 VALUES ('$sha', '$project_id', '$author', '$message', $timestamp);"
    done
}

# Get sync state for a project
# Usage: db_get_sync_state "github:user/repo"
db_get_sync_state() {
    local project_id="$1"
    db_query "SELECT * FROM sync_state WHERE project_id = '$project_id'" | jq '.[0] // {}'
}

# Update sync state
# Usage: db_set_sync_state "github:user/repo" "commits_cursor" "abc123"
db_set_sync_state() {
    local project_id="$1"
    local field="$2"
    local value="$3"
    
    db_exec "INSERT INTO sync_state (project_id, $field)
             VALUES ('$project_id', '$value')
             ON CONFLICT(project_id) DO UPDATE SET $field = '$value';"
}

# Get all projects
db_get_projects() {
    db_query "SELECT * FROM projects ORDER BY priority DESC, name"
}

# Get project by ID or name (fuzzy match)
db_get_project() {
    local search="$1"
    db_query "SELECT * FROM projects 
              WHERE id = '$search' 
                 OR name LIKE '%$search%' 
                 OR id LIKE '%$search%'
              LIMIT 1" | jq '.[0] // null'
}

# Get recent commits for a project
# Usage: db_get_commits "github:user/repo" 30
db_get_commits() {
    local project_id="$1"
    local days="${2:-90}"
    local since=$(($(date +%s) - days * 86400))
    
    db_query "SELECT * FROM commits 
              WHERE project_id = '$project_id' AND timestamp > $since
              ORDER BY timestamp DESC"
}

# Get commit stats for a project
db_get_commit_stats() {
    local project_id="$1"
    local days="${2:-7}"
    local since=$(($(date +%s) - days * 86400))
    
    db_query "SELECT 
                COUNT(*) as commit_count,
                COUNT(DISTINCT author) as author_count,
                MAX(timestamp) as last_commit
              FROM commits 
              WHERE project_id = '$project_id' AND timestamp > $since"
}

# Get open PRs for a project
db_get_open_prs() {
    local project_id="$1"
    db_query "SELECT * FROM pull_requests 
              WHERE project_id = '$project_id' AND state = 'open'
              ORDER BY updated_at DESC"
}

# Get open issues for a project
db_get_open_issues() {
    local project_id="$1"
    db_query "SELECT * FROM issues 
              WHERE project_id = '$project_id' AND state = 'open'
              ORDER BY updated_at DESC"
}

# Cache an analysis result
# Usage: db_cache_analysis "github:user/repo" "agent_gaps" "$result_json" 604800
db_cache_analysis() {
    local project_id="$1"
    local type="$2"
    local result="$3"
    local ttl_seconds="${4:-86400}"  # Default 24 hours
    local input_hash="${5:-}"
    
    local now=$(date +%s)
    local valid_until=$((now + ttl_seconds))
    
    # Escape JSON for SQL
    result=$(echo "$result" | sed "s/'/''/g")
    
    db_exec "INSERT INTO analyses (project_id, type, input_hash, result, created_at, valid_until)
             VALUES ('$project_id', '$type', '$input_hash', '$result', $now, $valid_until);"
}

# Get cached analysis (if valid)
# Usage: db_get_cached_analysis "github:user/repo" "agent_gaps" "$input_hash"
db_get_cached_analysis() {
    local project_id="$1"
    local type="$2"
    local input_hash="${3:-}"
    
    local now=$(date +%s)
    
    local where_hash=""
    [[ -n "$input_hash" ]] && where_hash="AND input_hash = '$input_hash'"
    
    db_query "SELECT result FROM analyses 
              WHERE project_id = '$project_id' 
                AND type = '$type'
                AND valid_until > $now
                $where_hash
              ORDER BY created_at DESC
              LIMIT 1" | jq -r '.[0].result // empty'
}
