#!/usr/bin/env bash
# Provider interface definition for god-mode
# Each provider (github, azure, gitlab) implements these functions

# Provider Interface:
#
# provider_check_auth()
#   Returns: JSON { available: bool, authenticated: bool, user: string }
#   Checks if the provider CLI is installed and authenticated
#
# provider_list_repos([limit])
#   Returns: JSON array of { id, name, description, default_branch }
#   Lists repositories accessible to the authenticated user
#
# provider_fetch_commits(repo, [since_date])
#   Returns: JSON array of { sha, author, message, date }
#   Fetches commits, optionally since a date (ISO 8601)
#
# provider_fetch_prs(repo, [state])
#   Returns: JSON array of { id, number, title, state, author, created_at, updated_at }
#   Fetches pull requests/merge requests
#
# provider_fetch_issues(repo, [state])
#   Returns: JSON array of { id, number, title, state, author, created_at, updated_at }
#   Fetches issues/work items
#
# provider_get_repo(repo)
#   Returns: JSON { name, description, default_branch, visibility, last_push }
#   Gets repository metadata

# Helper: dispatch to correct provider
# Usage: provider_call "github" "check_auth"
provider_call() {
    local provider="$1"
    local func="$2"
    shift 2

    case "$provider" in
        github)
            "github_${func}" "$@"
            ;;
        azure)
            "azure_${func}" "$@"
            ;;
        gitlab)
            "gitlab_${func}" "$@"
            ;;
        *)
            echo '{"error": "Unknown provider: '"$provider"'"}'
            return 1
            ;;
    esac
}

# Check if a provider is supported
provider_supported() {
    local provider="$1"
    case "$provider" in
        github) return 0 ;;
        azure|gitlab) return 1 ;;  # Stubbed, not fully implemented
        *) return 1 ;;
    esac
}
