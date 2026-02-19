#!/usr/bin/env bash
# god projects - List and manage configured projects
# Usage: god projects [add|remove] [args]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"

# Source libraries
source "$LIB_DIR/output.sh"
source "$LIB_DIR/config.sh"
source "$LIB_DIR/db.sh"

# Show help
show_help() {
    cat << 'EOF'
Usage: god projects [command] [args]

List and manage configured projects.

Commands:
  (none)          List all configured projects
  add <uri>       Add a project to configuration
  remove <name>   Remove a project from configuration

Arguments:
  uri             Project URI: github:user/repo, azure:org/project/repo, etc.
  name            Project name or ID to remove

Options:
  --json          Output as JSON
  -h, --help      Show this help

Examples:
  god projects                          # List all projects
  god projects add github:user/repo     # Add a GitHub repo
  god projects add github:user/repo --name "My Project"
  god projects remove myproject         # Remove by name
EOF
}

# List all projects
list_projects() {
    local json_output="$1"

    local projects=$(config_get_projects)
    local count=$(echo "$projects" | jq 'length')

    if [[ "$json_output" == true ]]; then
        echo "$projects" | jq .
        return
    fi

    if [[ "$count" -eq 0 ]]; then
        warn "No projects configured."
        echo ""
        info "Add a project with:"
        echo "  god projects add github:user/repo"
        return
    fi

    header "Configured Projects"

    echo "$projects" | jq -c '.[]' | while read -r project; do
        local id=$(echo "$project" | jq -r '.id')
        local name=$(echo "$project" | jq -r '.name // ""')
        local priority=$(echo "$project" | jq -r '.priority // "medium"')
        local tags=$(echo "$project" | jq -r '.tags // [] | join(", ")')
        local local_path=$(echo "$project" | jq -r '.local // ""')

        # Display name or ID
        local display_name="${name:-$id}"

        # Priority indicator
        local priority_badge=""
        case "$priority" in
            high) priority_badge="${RED}●${RESET} " ;;
            low)  priority_badge="${DIM}○${RESET} " ;;
        esac

        echo -e "${priority_badge}${BOLD}${display_name}${RESET}"
        echo -e "  ${DIM}ID:${RESET} $id"
        [[ -n "$tags" ]] && echo -e "  ${DIM}Tags:${RESET} $tags"
        [[ -n "$local_path" ]] && echo -e "  ${DIM}Local:${RESET} $local_path"
        echo ""
    done

    echo -e "${DIM}$count project(s) configured${RESET}"
}

# Add a project
add_project() {
    local uri="$1"
    local name=""
    local priority="medium"
    shift

    # Parse additional options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --name)
                name="$2"
                shift 2
                ;;
            --priority)
                priority="$2"
                shift 2
                ;;
            *)
                error "Unknown option: $1"
                return 1
                ;;
        esac
    done

    # Validate URI format
    if [[ ! "$uri" =~ ^(github|azure|gitlab|local): ]]; then
        error "Invalid project URI format"
        echo ""
        info "Expected format: provider:path"
        echo "  github:user/repo"
        echo "  azure:org/project/repo"
        echo "  gitlab:group/repo"
        echo "  local:~/code/myproject"
        return 1
    fi

    local provider=$(config_parse_provider "$uri")

    # Check provider support
    case "$provider" in
        github)
            # Validate GitHub repo exists
            local repo=$(config_parse_repo "$uri")
            if command -v gh &>/dev/null; then
                echo -n "Checking repository... "
                if gh repo view "$repo" &>/dev/null; then
                    success "Found"
                else
                    error "Repository not found or not accessible: $repo"
                    return 1
                fi
            fi
            ;;
        azure|gitlab)
            warn "Provider '$provider' support coming soon. Adding anyway."
            ;;
        local)
            local path=$(config_parse_repo "$uri")
            path="${path/#\~/$HOME}"
            if [[ ! -d "$path" ]]; then
                error "Local path does not exist: $path"
                return 1
            fi
            ;;
    esac

    # Add to config
    config_add_project "$uri" "$name" "$priority"

    # Also add to database
    db_init
    db_upsert_project "$uri" "$provider" "${name:-$uri}" "$priority" "[]" ""

    echo ""
    info "Run 'god sync' to fetch data for this project"
}

# Remove a project
remove_project() {
    local search="$1"

    # Find the project first
    local project=$(config_get_project "$search")
    if [[ -z "$project" || "$project" == "null" ]]; then
        error "Project not found: $search"
        return 1
    fi

    local id=$(echo "$project" | jq -r '.id')
    local name=$(echo "$project" | jq -r '.name // .id')

    # Confirm removal
    echo -e "Remove ${BOLD}${name}${RESET} ($id)?"
    echo -n "Type 'yes' to confirm: "
    read -r confirm

    if [[ "$confirm" != "yes" ]]; then
        echo "Cancelled."
        return 0
    fi

    # Remove from config
    config_remove_project "$id"

    # Optionally remove from database
    echo -n "Also remove cached data? [y/N] "
    read -r remove_data

    if [[ "$remove_data" =~ ^[Yy] ]]; then
        db_init
        db_exec "DELETE FROM commits WHERE project_id = '$id';"
        db_exec "DELETE FROM pull_requests WHERE project_id = '$id';"
        db_exec "DELETE FROM issues WHERE project_id = '$id';"
        db_exec "DELETE FROM sync_state WHERE project_id = '$id';"
        db_exec "DELETE FROM analyses WHERE project_id = '$id';"
        db_exec "DELETE FROM projects WHERE id = '$id';"
        success "Removed project and cached data"
    else
        success "Removed project (cached data retained)"
    fi
}

# Main
JSON_OUTPUT=false

# Handle --json flag anywhere in args
for arg in "$@"; do
    [[ "$arg" == "--json" ]] && JSON_OUTPUT=true
done

# Remove --json from args for processing
args=()
for arg in "$@"; do
    [[ "$arg" != "--json" ]] && args+=("$arg")
done
set -- "${args[@]+"${args[@]}"}"

case "${1:-}" in
    -h|--help|help)
        show_help
        ;;
    add)
        shift
        if [[ $# -lt 1 ]]; then
            error "Missing project URI"
            echo "Usage: god projects add <uri>"
            exit 1
        fi
        add_project "$@"
        ;;
    remove|rm)
        shift
        if [[ $# -lt 1 ]]; then
            error "Missing project name"
            echo "Usage: god projects remove <name>"
            exit 1
        fi
        remove_project "$1"
        ;;
    "")
        list_projects "$JSON_OUTPUT"
        ;;
    *)
        error "Unknown command: $1"
        echo "Run 'god projects --help' for usage."
        exit 1
        ;;
esac
