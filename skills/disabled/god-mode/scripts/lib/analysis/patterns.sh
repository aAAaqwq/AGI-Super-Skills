#!/usr/bin/env bash
# Commit pattern extraction for agent analysis
# Analyzes commit history to identify work patterns

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../db.sh"

# Extract commit types from conventional commit messages
# Usage: extract_commit_types "github:user/repo" [days]
# Returns: JSON { feat: N, fix: N, docs: N, test: N, refactor: N, chore: N, other: N }
extract_commit_types() {
    local project_id="$1"
    local days="${2:-90}"
    local since=$(($(date +%s) - days * 86400))

    # Get commits from database
    local commits=$(db_query "SELECT message FROM commits
                              WHERE project_id = '$project_id' AND timestamp > $since")

    # Count by conventional commit type
    local feat=0 fix=0 docs=0 test=0 refactor=0 chore=0 style=0 perf=0 ci=0 build=0 other=0
    local total=0

    while read -r msg; do
        ((total++)) || true
        msg_lower=$(echo "$msg" | tr '[:upper:]' '[:lower:]')

        case "$msg_lower" in
            feat:*|feat\(*) ((feat++)) ;;
            fix:*|fix\(*|bugfix:*) ((fix++)) ;;
            docs:*|doc:*) ((docs++)) ;;
            test:*|tests:*) ((test++)) ;;
            refactor:*|refact:*) ((refactor++)) ;;
            chore:*) ((chore++)) ;;
            style:*) ((style++)) ;;
            perf:*|performance:*) ((perf++)) ;;
            ci:*) ((ci++)) ;;
            build:*) ((build++)) ;;
            *) ((other++)) ;;
        esac
    done < <(echo "$commits" | jq -r '.[].message // empty' 2>/dev/null)

    jq -n \
        --argjson feat "$feat" \
        --argjson fix "$fix" \
        --argjson docs "$docs" \
        --argjson test "$test" \
        --argjson refactor "$refactor" \
        --argjson chore "$chore" \
        --argjson style "$style" \
        --argjson perf "$perf" \
        --argjson ci "$ci" \
        --argjson build "$build" \
        --argjson other "$other" \
        --argjson total "$total" \
        '{
            feat: $feat,
            fix: $fix,
            docs: $docs,
            test: $test,
            refactor: $refactor,
            chore: $chore,
            style: $style,
            perf: $perf,
            ci: $ci,
            build: $build,
            other: $other,
            total: $total
        }'
}

# Identify churn commits (quick fixes, reverts, typos)
# Usage: extract_churn_commits "github:user/repo" [days]
# Returns: JSON { count: N, percentage: N, examples: [...] }
extract_churn_commits() {
    local project_id="$1"
    local days="${2:-90}"
    local since=$(($(date +%s) - days * 86400))

    local commits=$(db_query "SELECT sha, message FROM commits
                              WHERE project_id = '$project_id' AND timestamp > $since")

    local total=$(echo "$commits" | jq 'length')
    local churn_count=0
    local examples="[]"

    while read -r commit; do
        local sha=$(echo "$commit" | jq -r '.sha')
        local msg=$(echo "$commit" | jq -r '.message' | head -1)
        local msg_lower=$(echo "$msg" | tr '[:upper:]' '[:lower:]')

        # Check for churn patterns
        local is_churn=false
        case "$msg_lower" in
            *revert*|*undo*) is_churn=true ;;
            *typo*|*typos*) is_churn=true ;;
            *oops*|*whoops*) is_churn=true ;;
            "fix "*|"fixed "*)
                # Short fix messages often indicate quick patches
                [[ ${#msg} -lt 20 ]] && is_churn=true
                ;;
            *"forgot"*|*"missing"*) is_churn=true ;;
            *"wip"*|*"work in progress"*) is_churn=true ;;
        esac

        if [[ "$is_churn" == true ]]; then
            ((churn_count++)) || true
            # Keep first 5 examples
            if [[ $(echo "$examples" | jq 'length') -lt 5 ]]; then
                examples=$(echo "$examples" | jq --arg sha "${sha:0:7}" --arg msg "$msg" \
                    '. += [{sha: $sha, message: $msg}]')
            fi
        fi
    done < <(echo "$commits" | jq -c '.[]' 2>/dev/null)

    local percentage=0
    [[ $total -gt 0 ]] && percentage=$((churn_count * 100 / total))

    jq -n \
        --argjson count "$churn_count" \
        --argjson percentage "$percentage" \
        --argjson total "$total" \
        --argjson examples "$examples" \
        '{
            count: $count,
            percentage: $percentage,
            total_commits: $total,
            examples: $examples
        }'
}

# Extract frequently mentioned topics/keywords from commit messages
# Usage: extract_topics "github:user/repo" [days]
# Returns: JSON array of {topic: string, count: number}
extract_topics() {
    local project_id="$1"
    local days="${2:-90}"
    local since=$(($(date +%s) - days * 86400))

    local commits=$(db_query "SELECT message FROM commits
                              WHERE project_id = '$project_id' AND timestamp > $since")

    # Common topic keywords to look for
    local topics=(
        "test" "tests" "testing"
        "api" "endpoint" "route"
        "auth" "authentication" "login" "oauth"
        "error" "errors" "exception" "handling"
        "database" "db" "sql" "query"
        "ui" "ux" "frontend" "component"
        "deploy" "deployment" "ci" "cd"
        "security" "vulnerability" "xss" "injection"
        "performance" "perf" "optimize" "cache"
        "config" "configuration" "settings"
        "docker" "kubernetes" "container"
        "logging" "log" "debug"
        "documentation" "docs" "readme"
        "dependency" "dependencies" "upgrade" "update"
    )

    # Build topic counts
    local result="[]"

    for topic in "${topics[@]}"; do
        local count=$(echo "$commits" | jq -r '.[].message // empty' | \
            grep -ic "\b${topic}\b" 2>/dev/null || echo "0")
        if [[ $count -gt 0 ]]; then
            result=$(echo "$result" | jq --arg t "$topic" --argjson c "$count" \
                '. += [{topic: $t, count: $c}]')
        fi
    done

    # Sort by count descending, take top 10
    echo "$result" | jq 'sort_by(-.count) | .[0:10]'
}

# Get author activity breakdown
# Usage: extract_authors "github:user/repo" [days]
# Returns: JSON array of {author: string, commits: number, percentage: number}
extract_authors() {
    local project_id="$1"
    local days="${2:-90}"
    local since=$(($(date +%s) - days * 86400))

    db_query "SELECT author, COUNT(*) as commits
              FROM commits
              WHERE project_id = '$project_id' AND timestamp > $since
              GROUP BY author
              ORDER BY commits DESC
              LIMIT 10" | jq '
        . as $all |
        ($all | map(.commits) | add) as $total |
        $all | map(. + {percentage: ((.commits / $total) * 100 | floor)})
    '
}

# Build a complete pattern summary for LLM prompt
# Usage: build_pattern_summary "github:user/repo" [days]
# Returns: JSON with all pattern data
build_pattern_summary() {
    local project_id="$1"
    local days="${2:-90}"

    local commit_types=$(extract_commit_types "$project_id" "$days")
    local churn=$(extract_churn_commits "$project_id" "$days")
    local topics=$(extract_topics "$project_id" "$days")
    local authors=$(extract_authors "$project_id" "$days")

    # Get basic stats
    local since=$(($(date +%s) - days * 86400))
    local stats=$(db_query "SELECT
                              COUNT(*) as total_commits,
                              COUNT(DISTINCT author) as unique_authors,
                              MIN(timestamp) as first_commit,
                              MAX(timestamp) as last_commit
                           FROM commits
                           WHERE project_id = '$project_id' AND timestamp > $since")

    # Calculate activity metrics
    local total=$(echo "$commit_types" | jq '.total')
    local feat_pct=0 fix_pct=0 test_pct=0
    if [[ $total -gt 0 ]]; then
        feat_pct=$(echo "$commit_types" | jq "(.feat / $total * 100) | floor")
        fix_pct=$(echo "$commit_types" | jq "(.fix / $total * 100) | floor")
        test_pct=$(echo "$commit_types" | jq "(.test / $total * 100) | floor")
    fi

    jq -n \
        --arg project_id "$project_id" \
        --argjson days "$days" \
        --argjson stats "$(echo "$stats" | jq '.[0] // {}')" \
        --argjson commit_types "$commit_types" \
        --argjson churn "$churn" \
        --argjson topics "$topics" \
        --argjson authors "$authors" \
        --argjson feat_pct "$feat_pct" \
        --argjson fix_pct "$fix_pct" \
        --argjson test_pct "$test_pct" \
        '{
            project_id: $project_id,
            analysis_window_days: $days,
            stats: $stats,
            commit_types: $commit_types,
            type_percentages: {
                features: $feat_pct,
                fixes: $fix_pct,
                tests: $test_pct
            },
            churn: $churn,
            top_topics: $topics,
            top_authors: $authors
        }'
}

# Generate human-readable pattern summary
# Usage: format_pattern_summary "github:user/repo" [days]
format_pattern_summary() {
    local project_id="$1"
    local days="${2:-90}"

    local summary=$(build_pattern_summary "$project_id" "$days")

    local total=$(echo "$summary" | jq '.commit_types.total')
    local feat=$(echo "$summary" | jq '.commit_types.feat')
    local fix=$(echo "$summary" | jq '.commit_types.fix')
    local test=$(echo "$summary" | jq '.commit_types.test')
    local churn_pct=$(echo "$summary" | jq '.churn.percentage')

    echo "## Commit Patterns (last $days days)"
    echo ""
    echo "Total commits: $total"
    echo ""
    echo "### By Type"
    echo "- Features: $feat ($( echo "$summary" | jq '.type_percentages.features')%)"
    echo "- Bug fixes: $fix ($( echo "$summary" | jq '.type_percentages.fixes')%)"
    echo "- Tests: $test ($( echo "$summary" | jq '.type_percentages.tests')%)"
    echo ""

    if [[ "$churn_pct" -gt 10 ]]; then
        echo "### ⚠️ Churn Alert"
        echo "- $churn_pct% of commits are quick fixes, reverts, or typo corrections"
        echo ""
    fi

    echo "### Top Topics"
    echo "$summary" | jq -r '.top_topics[] | "- \(.topic): \(.count) mentions"'
}
