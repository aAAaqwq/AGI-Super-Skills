#!/usr/bin/env bash
# god agents - Analyze and improve agent instructions
# Usage: god agents analyze <project>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"
PROMPTS_DIR="$SCRIPT_DIR/../../prompts"

# Source libraries
source "$LIB_DIR/output.sh"
source "$LIB_DIR/config.sh"
source "$LIB_DIR/db.sh"
source "$LIB_DIR/analysis/patterns.sh"
source "$LIB_DIR/analysis/agents.sh"

# Show help
show_help() {
    cat << 'EOF'
Usage: god agents <command> [project]

Analyze and improve AI agent instructions.

Commands:
  analyze <project>   Analyze agents.md against commit patterns
  show <project>      Show current agent file content
  generate <project>  Generate agents.md for a new project (coming soon)

Options:
  --force             Force re-analysis (ignore cache)
  --json              Output as JSON
  -h, --help          Show this help

Examples:
  god agents analyze myproject    # Analyze and suggest improvements
  god agents show myproject       # View current agent file
EOF
}

# Analyze agent file against commit patterns
analyze_project() {
    local project_filter="$1"
    local force="${2:-false}"
    local json_output="${3:-false}"

    # Find project
    local project=$(config_get_project "$project_filter")
    if [[ -z "$project" || "$project" == "null" ]]; then
        error "Project not found: $project_filter"
        exit 1
    fi

    local project_id=$(echo "$project" | jq -r '.id')
    local project_name=$(echo "$project" | jq -r '.name // .id')
    local repo=$(config_parse_repo "$project_id")

    if [[ "$json_output" != "true" ]]; then
        header "Analyzing $project_name"
    fi

    # Get agent file content
    if [[ "$json_output" != "true" ]]; then
        echo -n "Finding agent file... "
    fi

    local agent_data=$(get_agent_content "$project_id")
    if [[ "$agent_data" == "null" ]]; then
        if [[ "$json_output" == "true" ]]; then
            jq -n '{error: "No agent file found", suggestions: ["Create an agents.md file in your repository"]}'
        else
            warn "No agent file found"
            echo ""
            info "Create one of these files in your repo:"
            echo "  - agents.md"
            echo "  - CLAUDE.md"
            echo "  - .github/copilot-instructions.md"
        fi
        return 1
    fi

    local agent_path=$(echo "$agent_data" | jq -r '.path')
    local agent_content=$(echo "$agent_data" | jq -r '.content')
    local agent_source=$(echo "$agent_data" | jq -r '.source')

    if [[ "$json_output" != "true" ]]; then
        success "Found $agent_path ($agent_source)"
    fi

    # Check cache
    local content_hash=$(hash_agent_content "$agent_content")
    if [[ "$force" != "true" ]]; then
        local cached=$(db_get_cached_analysis "$project_id" "agent_gaps" "$content_hash")
        if [[ -n "$cached" ]]; then
            if [[ "$json_output" == "true" ]]; then
                echo "$cached"
            else
                info "Using cached analysis (agent file unchanged)"
                echo ""
                display_analysis "$cached"
            fi
            return 0
        fi
    fi

    # Build commit pattern summary
    if [[ "$json_output" != "true" ]]; then
        echo -n "Analyzing commit patterns... "
    fi

    local analysis_days=$(config_get "analysis.analysisWindowDays" "90")
    local patterns=$(build_pattern_summary "$project_id" "$analysis_days")
    local commit_count=$(echo "$patterns" | jq '.commit_types.total')

    if [[ "$commit_count" -eq 0 ]]; then
        if [[ "$json_output" == "true" ]]; then
            jq -n '{error: "No commits found", suggestions: ["Run god sync first to fetch commit history"]}'
        else
            warn "No commits in database"
            info "Run 'god sync $project_filter' first to fetch commit history"
        fi
        return 1
    fi

    if [[ "$json_output" != "true" ]]; then
        success "$commit_count commits analyzed"
    fi

    # Build prompt for LLM
    local prompt_template
    prompt_template=$(cat "$PROMPTS_DIR/agent-analysis.md")

    # Fill in template variables
    local commit_types_formatted=$(echo "$patterns" | jq -r '
        .commit_types |
        "- Features (feat): \(.feat)\n- Bug fixes (fix): \(.fix)\n- Tests: \(.test)\n- Docs: \(.docs)\n- Refactoring: \(.refactor)\n- Chores: \(.chore)\n- Other: \(.other)"
    ')

    local churn_info=$(echo "$patterns" | jq -r '
        .churn |
        "Churn commits: \(.count) (\(.percentage)% of total)"
    ')

    local topics_formatted=$(echo "$patterns" | jq -r '
        .top_topics | map("- \(.topic): \(.count) mentions") | join("\n")
    ')

    # Get sample commit messages
    local commit_samples=$(db_query "SELECT message FROM commits
                                     WHERE project_id = '$project_id'
                                     ORDER BY timestamp DESC
                                     LIMIT 10" | jq -r '.[].message | split("\n")[0]' | head -10)

    # Build the complete prompt
    local prompt="$prompt_template"
    prompt="${prompt//\{\{ project_name \}\}/$project_name}"
    prompt="${prompt//\{\{ repository \}\}/$repo}"
    prompt="${prompt//\{\{ days \}\}/$analysis_days}"
    prompt="${prompt//\{\{ commit_count \}\}/$commit_count}"
    prompt="${prompt//\{\{ agent_content \}\}/$agent_content}"
    prompt="${prompt//\{\{ commit_types \}\}/$commit_types_formatted}"
    prompt="${prompt//\{\{ file_patterns \}\}/$topics_formatted}"
    prompt="${prompt//\{\{ revert_count \}\}/$(echo "$patterns" | jq '.churn.count')}"
    prompt="${prompt//\{\{ typo_fix_count \}\}/$(echo "$patterns" | jq '.churn.count')}"
    prompt="${prompt//\{\{ repeated_patterns \}\}/See topics above}"
    prompt="${prompt//\{\{ commit_samples \}\}/$commit_samples}"

    # Output the prompt for the LLM (OpenClaw will handle the actual LLM call)
    if [[ "$json_output" != "true" ]]; then
        echo ""
        divider
        echo ""
        echo "## Analysis Request"
        echo ""
        echo "The following prompt should be sent to an LLM for analysis."
        echo "In OpenClaw, this will be handled automatically."
        echo ""
        divider
    fi

    # For now, output the prompt so OpenClaw/user can process it
    # In a full integration, this would call the LLM directly
    echo ""
    echo "$prompt"

    # Store agent snapshot
    store_agent_snapshot "$project_id" "$agent_path" "$agent_content"
}

# Show agent file content
show_agent() {
    local project_filter="$1"
    local json_output="${2:-false}"

    local project=$(config_get_project "$project_filter")
    if [[ -z "$project" || "$project" == "null" ]]; then
        error "Project not found: $project_filter"
        exit 1
    fi

    local project_id=$(echo "$project" | jq -r '.id')
    local project_name=$(echo "$project" | jq -r '.name // .id')

    local agent_data=$(get_agent_content "$project_id")
    if [[ "$agent_data" == "null" ]]; then
        if [[ "$json_output" == "true" ]]; then
            jq -n '{error: "No agent file found"}'
        else
            error "No agent file found for $project_name"
        fi
        return 1
    fi

    if [[ "$json_output" == "true" ]]; then
        echo "$agent_data"
    else
        local agent_path=$(echo "$agent_data" | jq -r '.path')
        local agent_content=$(echo "$agent_data" | jq -r '.content')
        local agent_source=$(echo "$agent_data" | jq -r '.source')

        header "$project_name - $agent_path"
        echo -e "${DIM}Source: $agent_source${RESET}"
        echo ""
        divider
        echo ""
        echo "$agent_content"
    fi
}

# Display analysis results (from cache or LLM response)
display_analysis() {
    local analysis="$1"

    # Check if it's valid JSON
    if ! echo "$analysis" | jq . &>/dev/null; then
        echo "$analysis"
        return
    fi

    # Display gaps
    local gaps=$(echo "$analysis" | jq '.gaps // []')
    local gap_count=$(echo "$gaps" | jq 'length')

    if [[ "$gap_count" -gt 0 ]]; then
        echo ""
        echo -e "${YELLOW}${BOLD}⚠️ GAPS FOUND${RESET}"
        echo ""
        echo "$gaps" | jq -r '.[] | "  \(.area) (\(.impact) impact)\n    \(.observation)\n    → \(.suggestion)\n"'
    fi

    # Display strengths
    local strengths=$(echo "$analysis" | jq '.strengths // []')
    local strength_count=$(echo "$strengths" | jq 'length')

    if [[ "$strength_count" -gt 0 ]]; then
        echo ""
        echo -e "${GREEN}${BOLD}✅ WORKING WELL${RESET}"
        echo ""
        echo "$strengths" | jq -r '.[] | "  \(.area)\n    \(.observation)\n"'
    fi

    # Display recommendations
    local recs=$(echo "$analysis" | jq '.recommendations // []')
    local rec_count=$(echo "$recs" | jq 'length')

    if [[ "$rec_count" -gt 0 ]]; then
        echo ""
        echo -e "${CYAN}${BOLD}📝 SUGGESTED ADDITIONS${RESET}"
        echo ""
        echo "$recs" | jq -r 'sort_by(.priority) | .[] | "\(.section)\n\(.content)\n"'
    fi

    # Summary
    local summary=$(echo "$analysis" | jq -r '.summary // ""')
    if [[ -n "$summary" ]]; then
        echo ""
        divider
        echo ""
        echo "$summary"
    fi
}

# Main
FORCE=false
JSON_OUTPUT=false

# Process flags
args=()
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=true ;;
        --json) JSON_OUTPUT=true ;;
        *) args+=("$arg") ;;
    esac
done
set -- "${args[@]+"${args[@]}"}"

case "${1:-}" in
    -h|--help|help)
        show_help
        ;;
    analyze)
        shift
        if [[ $# -lt 1 ]]; then
            error "Missing project name"
            echo "Usage: god agents analyze <project>"
            exit 1
        fi
        db_init
        analyze_project "$1" "$FORCE" "$JSON_OUTPUT"
        ;;
    show)
        shift
        if [[ $# -lt 1 ]]; then
            error "Missing project name"
            echo "Usage: god agents show <project>"
            exit 1
        fi
        show_agent "$1" "$JSON_OUTPUT"
        ;;
    generate)
        warn "Generate feature coming soon!"
        info "For now, create an agents.md manually and use 'god agents analyze' to improve it."
        ;;
    "")
        show_help
        ;;
    *)
        # Assume it's a project name for analyze
        db_init
        analyze_project "$1" "$FORCE" "$JSON_OUTPUT"
        ;;
esac
