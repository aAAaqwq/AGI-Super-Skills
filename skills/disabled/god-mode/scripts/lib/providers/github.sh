#!/usr/bin/env bash
# GitHub provider for god-mode
# Uses `gh` CLI for authentication and API calls

# Check if gh CLI is available and authenticated
# Returns: JSON { available: bool, authenticated: bool, user: string }
github_check_auth() {
    if ! command -v gh &>/dev/null; then
        echo '{"available":false,"authenticated":false,"user":null}'
        return 1
    fi
    
    if gh auth status &>/dev/null; then
        local user
        user=$(gh api user --jq '.login' 2>/dev/null || echo "")
        echo "{\"available\":true,\"authenticated\":true,\"user\":\"$user\"}"
        return 0
    else
        echo '{"available":true,"authenticated":false,"user":null}'
        return 1
    fi
}

# List accessible repositories
# Usage: github_list_repos [limit]
github_list_repos() {
    local limit="${1:-100}"
    gh repo list --limit "$limit" --json nameWithOwner,name,description,defaultBranchRef \
        --jq '[.[] | {id: ("github:" + .nameWithOwner), name: .name, description: .description, default_branch: .defaultBranchRef.name}]'
}

# Fetch commits for a repo
# Usage: github_fetch_commits "user/repo" [since_date]
# since_date: ISO 8601 format (e.g., 2026-01-01T00:00:00Z)
github_fetch_commits() {
    local repo="$1"
    local since="${2:-}"
    
    local since_param=""
    [[ -n "$since" ]] && since_param="--since=$since"
    
    # Use gh api for more control
    local query="repos/$repo/commits?per_page=100"
    [[ -n "$since" ]] && query="${query}&since=$since"
    
    gh api "$query" --paginate \
        --jq '[.[] | {
            sha: .sha,
            author: (.commit.author.name // .author.login // "unknown"),
            author_email: .commit.author.email,
            message: .commit.message,
            date: .commit.author.date,
            files_changed: (.files | length // 0)
        }]' 2>/dev/null || echo "[]"
}

# Fetch pull requests
# Usage: github_fetch_prs "user/repo" [state]
# state: open, closed, merged, all (default: all)
github_fetch_prs() {
    local repo="$1"
    local state="${2:-all}"
    
    gh pr list --repo "$repo" --state "$state" --limit 100 \
        --json number,title,state,author,createdAt,updatedAt,mergedAt,reviewRequests,labels \
        --jq '[.[] | {
            id: ("github:" + "'"$repo"'" + ":" + (.number | tostring)),
            number: .number,
            title: .title,
            state: .state,
            author: .author.login,
            created_at: .createdAt,
            updated_at: .updatedAt,
            merged_at: .mergedAt,
            reviewers: [.reviewRequests[].login],
            labels: [.labels[].name]
        }]' 2>/dev/null || echo "[]"
}

# Fetch issues
# Usage: github_fetch_issues "user/repo" [state]
# state: open, closed, all (default: all)
github_fetch_issues() {
    local repo="$1"
    local state="${2:-all}"
    
    gh issue list --repo "$repo" --state "$state" --limit 100 \
        --json number,title,state,author,assignees,createdAt,updatedAt,closedAt,labels \
        --jq '[.[] | {
            id: ("github:" + "'"$repo"'" + ":" + (.number | tostring)),
            number: .number,
            title: .title,
            state: .state,
            author: .author.login,
            assignee: (.assignees[0].login // null),
            created_at: .createdAt,
            updated_at: .updatedAt,
            closed_at: .closedAt,
            labels: [.labels[].name]
        }]' 2>/dev/null || echo "[]"
}

# Get repository metadata
# Usage: github_get_repo "user/repo"
github_get_repo() {
    local repo="$1"
    
    gh repo view "$repo" --json name,description,defaultBranchRef,visibility,pushedAt \
        --jq '{
            name: .name,
            description: .description,
            default_branch: .defaultBranchRef.name,
            visibility: .visibility,
            last_push: .pushedAt
        }' 2>/dev/null || echo "{}"
}

# Get the repo identifier from various formats
# Input: "github:user/repo" or "user/repo" or "https://github.com/user/repo"
# Output: "user/repo"
github_normalize_repo() {
    local input="$1"
    
    # Remove github: prefix
    input="${input#github:}"
    
    # Remove https://github.com/ prefix
    input="${input#https://github.com/}"
    
    # Remove trailing .git
    input="${input%.git}"
    
    # Remove trailing slashes
    input="${input%/}"
    
    echo "$input"
}
