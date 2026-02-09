-- god-mode skill database schema
-- Location: ~/.god-mode/cache.db

-- Provider auth status (NOT tokens - just status)
CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,            -- 'github', 'azure', 'gitlab'
    cli_available INTEGER DEFAULT 0,
    authenticated INTEGER DEFAULT 0,
    username TEXT,
    orgs TEXT,                      -- JSON array of accessible orgs
    last_checked INTEGER            -- Unix timestamp
);

-- Configured projects
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,            -- 'github:user/repo' or 'azure:org/project/repo'
    provider TEXT NOT NULL,         -- 'github', 'azure', 'gitlab', 'local'
    name TEXT,                      -- Display name
    local_path TEXT,                -- Local clone path (optional)
    priority TEXT DEFAULT 'medium', -- 'high', 'medium', 'low'
    tags TEXT,                      -- JSON array
    default_branch TEXT,
    last_synced INTEGER,
    config TEXT                     -- JSON blob for extra settings
);

-- Cached commits (incremental sync)
CREATE TABLE IF NOT EXISTS commits (
    sha TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    author TEXT,
    author_email TEXT,
    message TEXT,
    timestamp INTEGER,              -- Unix timestamp
    files_changed INTEGER DEFAULT 0,
    insertions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_commits_project ON commits(project_id);
CREATE INDEX IF NOT EXISTS idx_commits_timestamp ON commits(timestamp);
CREATE INDEX IF NOT EXISTS idx_commits_project_timestamp ON commits(project_id, timestamp);

-- Cached pull requests / merge requests
CREATE TABLE IF NOT EXISTS pull_requests (
    id TEXT PRIMARY KEY,            -- 'github:user/repo:123'
    project_id TEXT NOT NULL,
    number INTEGER NOT NULL,
    title TEXT,
    state TEXT,                     -- 'open', 'merged', 'closed'
    author TEXT,
    created_at INTEGER,
    updated_at INTEGER,
    merged_at INTEGER,
    reviewers TEXT,                 -- JSON array
    labels TEXT,                    -- JSON array
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prs_project ON pull_requests(project_id);
CREATE INDEX IF NOT EXISTS idx_prs_state ON pull_requests(state);

-- Cached issues
CREATE TABLE IF NOT EXISTS issues (
    id TEXT PRIMARY KEY,            -- 'github:user/repo:456'
    project_id TEXT NOT NULL,
    number INTEGER NOT NULL,
    title TEXT,
    state TEXT,                     -- 'open', 'closed'
    author TEXT,
    assignee TEXT,
    created_at INTEGER,
    updated_at INTEGER,
    closed_at INTEGER,
    labels TEXT,                    -- JSON array
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_issues_project ON issues(project_id);
CREATE INDEX IF NOT EXISTS idx_issues_state ON issues(state);

-- Agent file snapshots (for tracking changes)
CREATE TABLE IF NOT EXISTS agent_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    path TEXT NOT NULL,             -- 'agents.md', '.github/copilot-instructions.md'
    content_hash TEXT,              -- For cache invalidation
    content TEXT,
    captured_at INTEGER,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_files_project ON agent_files(project_id);

-- Cached analysis results
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    type TEXT NOT NULL,             -- 'agent_gaps', 'activity_summary', 'health'
    input_hash TEXT,                -- Hash of inputs (for cache validation)
    result TEXT,                    -- JSON result
    created_at INTEGER,
    valid_until INTEGER,            -- Cache expiry timestamp
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analyses_project_type ON analyses(project_id, type);

-- Sync state for incremental updates
CREATE TABLE IF NOT EXISTS sync_state (
    project_id TEXT PRIMARY KEY,
    commits_cursor TEXT,            -- Last commit SHA or timestamp
    commits_synced_at INTEGER,
    prs_synced_at INTEGER,
    issues_synced_at INTEGER,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Context snapshots (for save/restore - v0.2)
CREATE TABLE IF NOT EXISTS contexts (
    project_id TEXT PRIMARY KEY,
    working_dir TEXT,
    branch TEXT,
    uncommitted_files TEXT,         -- JSON array
    open_files TEXT,                -- JSON array with line numbers
    active_issue_number INTEGER,
    active_issue_title TEXT,
    notes TEXT,
    saved_at INTEGER,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
