#!/usr/bin/env bash
# god status - Show overview of all projects
# Usage: god status [project]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"

# Source libraries
source "$LIB_DIR/output.sh"
source "$LIB_DIR/config.sh"
source "$LIB_DIR/db.sh"

# Parse arguments
PROJECT_FILTER=""
JSON_OUTPUT=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        -h|--help)
            cat << 'EOF'
Usage: god status [project] [options]

Show overview of all projects or details for one.

Arguments:
  project         Optional: show details for this project only

Options:
  --json          Output as JSON
  -h, --help      Show this help

Examples:
  god status                  # Overview of all projects
  god status myproject        # Details for one project
  god status --json           # JSON output for scripting
EOF
            exit 0
            ;;
        -*)
            error "Unknown option: $1"
            exit 1
            ;;
        *)
            PROJECT_FILTER="$1"
            shift
            ;;
    esac
done

# Initialize database (creates if not exists)
db_init

# Get projects
if [[ -n "$PROJECT_FILTER" ]]; then
    # Single project detail view
    PROJECT=$(config_get_project "$PROJECT_FILTER")
    if [[ -z "$PROJECT" || "$PROJECT" == "null" ]]; then
        error "Project not found: $PROJECT_FILTER"
        exit 1
    fi
    show_project_detail "$PROJECT"
else
    # Multi-project overview
    show_overview
fi

# Show detailed view for a single project
show_project_detail() {
    local project="$1"
    local project_id=$(echo "$project" | jq -r '.id')
    local project_name=$(echo "$project" | jq -r '.name // .id')
    local priority=$(echo "$project" | jq -r '.priority // "medium"')

    if [[ "$JSON_OUTPUT" == true ]]; then
        # Build JSON response
        local commits=$(db_get_commits "$project_id" 30)
        local stats=$(db_get_commit_stats "$project_id" 7)
        local prs=$(db_get_open_prs "$project_id")
        local issues=$(db_get_open_issues "$project_id")

        jq -n \
            --arg id "$project_id" \
            --arg name "$project_name" \
            --arg priority "$priority" \
            --argjson commits "$commits" \
            --argjson stats "$stats" \
            --argjson prs "$prs" \
            --argjson issues "$issues" \
            '{
                id: $id,
                name: $name,
                priority: $priority,
                stats: $stats[0],
                open_prs: $prs,
                open_issues: $issues,
                recent_commits: ($commits | .[0:10])
            }'
        return
    fi

    header "$project_name"

    # Priority badge
    case "$priority" in
        high) echo -e "  ${RED}● HIGH PRIORITY${RESET}" ;;
        low)  echo -e "  ${DIM}○ low priority${RESET}" ;;
    esac
    echo ""

    # Stats
    local stats=$(db_get_commit_stats "$project_id" 7)
    local commit_count=$(echo "$stats" | jq -r '.[0].commit_count // 0')
    local author_count=$(echo "$stats" | jq -r '.[0].author_count // 0')
    local last_commit=$(echo "$stats" | jq -r '.[0].last_commit // 0')

    echo -e "${BOLD}This Week${RESET}"
    echo -e "  Commits: ${GREEN}$commit_count${RESET}"
    echo -e "  Authors: $author_count"
    if [[ "$last_commit" != "0" && "$last_commit" != "null" ]]; then
        echo -e "  Last activity: $(relative_time "$last_commit")"
    else
        echo -e "  Last activity: ${DIM}No data${RESET}"
    fi
    echo ""

    # Open PRs
    local prs=$(db_get_open_prs "$project_id")
    local pr_count=$(echo "$prs" | jq 'length')

    echo -e "${BOLD}Open Pull Requests${RESET} ($pr_count)"
    if [[ "$pr_count" -gt 0 ]]; then
        echo "$prs" | jq -r '.[] | "  #\(.number) \(.title) (\(.author))"' | head -5
        [[ "$pr_count" -gt 5 ]] && echo -e "  ${DIM}... and $((pr_count - 5)) more${RESET}"
    else
        echo -e "  ${DIM}None${RESET}"
    fi
    echo ""

    # Open issues
    local issues=$(db_get_open_issues "$project_id")
    local issue_count=$(echo "$issues" | jq 'length')

    echo -e "${BOLD}Open Issues${RESET} ($issue_count)"
    if [[ "$issue_count" -gt 0 ]]; then
        echo "$issues" | jq -r '.[] | "  #\(.number) \(.title)"' | head -5
        [[ "$issue_count" -gt 5 ]] && echo -e "  ${DIM}... and $((issue_count - 5)) more${RESET}"
    else
        echo -e "  ${DIM}None${RESET}"
    fi
    echo ""

    # Recent commits
    local commits=$(db_get_commits "$project_id" 7)
    local recent_count=$(echo "$commits" | jq 'length')

    echo -e "${BOLD}Recent Commits${RESET}"
    if [[ "$recent_count" -gt 0 ]]; then
        echo "$commits" | jq -r '.[0:5] | .[] | "  \(.sha[0:7]) \(.message | split("\n")[0] | .[0:50])"'
    else
        echo -e "  ${DIM}None in last 7 days${RESET}"
    fi
}

# Show overview of all projects
show_overview() {
    local projects=$(config_get_projects)
    local project_count=$(echo "$projects" | jq 'length')

    if [[ "$project_count" -eq 0 ]]; then
        if [[ "$JSON_OUTPUT" == true ]]; then
            echo '{"projects": [], "summary": {"total": 0}}'
            return
        fi
        warn "No projects configured."
        info "Add a project with: god projects add github:user/repo"
        return
    fi

    if [[ "$JSON_OUTPUT" == true ]]; then
        # Build JSON response
        local result="[]"
        while read -r project; do
            local project_id=$(echo "$project" | jq -r '.id')
            local project_name=$(echo "$project" | jq -r '.name // .id')
            local priority=$(echo "$project" | jq -r '.priority // "medium"')

            local stats=$(db_get_commit_stats "$project_id" 7)
            local prs=$(db_get_open_prs "$project_id")
            local issues=$(db_get_open_issues "$project_id")

            local pr_count=$(echo "$prs" | jq 'length')
            local issue_count=$(echo "$issues" | jq 'length')
            local commit_count=$(echo "$stats" | jq -r '.[0].commit_count // 0')
            local last_commit=$(echo "$stats" | jq -r '.[0].last_commit // 0')

            result=$(echo "$result" | jq --arg id "$project_id" \
                --arg name "$project_name" \
                --arg priority "$priority" \
                --argjson commits "$commit_count" \
                --argjson prs "$pr_count" \
                --argjson issues "$issue_count" \
                --argjson last "$last_commit" \
                '. += [{
                    id: $id,
                    name: $name,
                    priority: $priority,
                    commits_this_week: $commits,
                    open_prs: $prs,
                    open_issues: $issues,
                    last_commit: $last
                }]')
        done < <(echo "$projects" | jq -c '.[]')

        # Calculate summary
        local total_commits=$(echo "$result" | jq '[.[].commits_this_week] | add // 0')
        local total_prs=$(echo "$result" | jq '[.[].open_prs] | add // 0')

        jq -n --argjson projects "$result" \
            --argjson total_commits "$total_commits" \
            --argjson total_prs "$total_prs" \
            '{
                projects: $projects,
                summary: {
                    total_projects: ($projects | length),
                    total_commits_this_week: $total_commits,
                    total_open_prs: $total_prs
                }
            }'
        return
    fi

    header "god-mode"

    local total_commits=0
    local total_prs=0
    local stale_count=0
    local now=$(date +%s)
    local stale_threshold=$((5 * 86400))  # 5 days

    while read -r project; do
        local project_id=$(echo "$project" | jq -r '.id')
        local project_name=$(echo "$project" | jq -r '.name // .id')
        local priority=$(echo "$project" | jq -r '.priority // "medium"')

        # Get stats from database
        local stats=$(db_get_commit_stats "$project_id" 7)
        local commit_count=$(echo "$stats" | jq -r '.[0].commit_count // 0')
        local last_commit=$(echo "$stats" | jq -r '.[0].last_commit // 0')

        local prs=$(db_get_open_prs "$project_id")
        local pr_count=$(echo "$prs" | jq 'length')

        local issues=$(db_get_open_issues "$project_id")
        local issue_count=$(echo "$issues" | jq 'length')

        # Check if stale
        local is_stale=false
        local warning=""
        if [[ "$last_commit" != "0" && "$last_commit" != "null" ]]; then
            local age=$((now - last_commit))
            if [[ $age -gt $stale_threshold ]]; then
                is_stale=true
                warning="stale"
                ((stale_count++)) || true
            fi
        fi

        # Display project
        local name_display="$project_name"
        [[ "$priority" == "high" ]] && name_display="${RED}●${RESET} $name_display"
        [[ "$is_stale" == true ]] && name_display="$name_display ${YELLOW}⚠️${RESET}"

        echo -e "${BOLD}${name_display}${RESET}"

        # Last activity
        if [[ "$last_commit" != "0" && "$last_commit" != "null" ]]; then
            local last_msg=$(db_query "SELECT message FROM commits WHERE project_id='$project_id' ORDER BY timestamp DESC LIMIT 1" | jq -r '.[0].message // ""' | head -1 | cut -c1-40)
            echo -e "  Last: $(relative_time "$last_commit") • ${DIM}${last_msg}${RESET}"
        else
            echo -e "  Last: ${DIM}No activity synced${RESET}"
        fi

        # PR and issue counts
        local pr_display="$pr_count open"
        local issue_display="$issue_count"
        echo -e "  PRs: ${pr_display} • Issues: ${issue_display}"
        echo ""

        total_commits=$((total_commits + commit_count))
        total_prs=$((total_prs + pr_count))
    done < <(echo "$projects" | jq -c '.[]')

    # Summary
    divider
    echo -e "This week: ${GREEN}$total_commits commits${RESET} • $total_prs open PRs"
    [[ $stale_count -gt 0 ]] && warn "$stale_count project(s) with no recent activity"
}

# Run the appropriate view
if [[ -n "$PROJECT_FILTER" ]]; then
    PROJECT=$(config_get_project "$PROJECT_FILTER")
    if [[ -z "$PROJECT" || "$PROJECT" == "null" ]]; then
        error "Project not found: $PROJECT_FILTER"
        exit 1
    fi
    show_project_detail "$PROJECT"
else
    show_overview
fi
