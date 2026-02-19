#!/usr/bin/env bash
# Output formatting helpers for god-mode

# Colors (disable with NO_COLOR env var)
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    DIM='\033[2m'
    RESET='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' MAGENTA='' CYAN='' BOLD='' DIM='' RESET=''
fi

# Print colored text
# Usage: color red "Error message"
color() {
    local c="$1"
    shift
    case "$c" in
        red)     echo -e "${RED}$*${RESET}" ;;
        green)   echo -e "${GREEN}$*${RESET}" ;;
        yellow)  echo -e "${YELLOW}$*${RESET}" ;;
        blue)    echo -e "${BLUE}$*${RESET}" ;;
        magenta) echo -e "${MAGENTA}$*${RESET}" ;;
        cyan)    echo -e "${CYAN}$*${RESET}" ;;
        bold)    echo -e "${BOLD}$*${RESET}" ;;
        dim)     echo -e "${DIM}$*${RESET}" ;;
        *)       echo "$*" ;;
    esac
}

# Print a header
# Usage: header "My Section"
header() {
    echo ""
    color bold "🔭 $1"
    echo ""
}

# Print a section divider
divider() {
    color dim "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Print success message
success() {
    color green "✅ $*"
}

# Print warning message
warn() {
    color yellow "⚠️  $*"
}

# Print error message
error() {
    color red "❌ $*" >&2
}

# Print info message
info() {
    color cyan "ℹ️  $*"
}

# Print a project status line
# Usage: project_line "name" "last_commit" "prs" "issues" ["warning"]
project_line() {
    local name="$1"
    local last="$2"
    local prs="$3"
    local issues="$4"
    local warning="${5:-}"
    
    if [[ -n "$warning" ]]; then
        echo -e "${BOLD}${name}${RESET} ${YELLOW}⚠️${RESET}"
    else
        echo -e "${BOLD}${name}${RESET}"
    fi
    
    echo -e "  ${DIM}Last:${RESET} ${last}"
    echo -e "  ${DIM}PRs:${RESET} ${prs} ${DIM}•${RESET} ${DIM}Issues:${RESET} ${issues}"
}

# Format relative time
# Usage: relative_time 1706745600
relative_time() {
    local timestamp="$1"
    local now=$(date +%s)
    local diff=$((now - timestamp))
    
    if [[ $diff -lt 60 ]]; then
        echo "just now"
    elif [[ $diff -lt 3600 ]]; then
        echo "$((diff / 60))m ago"
    elif [[ $diff -lt 86400 ]]; then
        echo "$((diff / 3600))h ago"
    elif [[ $diff -lt 604800 ]]; then
        echo "$((diff / 86400))d ago"
    elif [[ $diff -lt 2592000 ]]; then
        echo "$((diff / 604800))w ago"
    else
        echo "$((diff / 2592000))mo ago"
    fi
}

# Spinner for long operations
# Usage: spin "Loading..." & pid=$!; do_work; kill $pid
spin() {
    local msg="${1:-Loading...}"
    local chars="⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    local i=0
    
    while true; do
        printf "\r${DIM}${chars:$i:1}${RESET} %s" "$msg"
        i=$(((i + 1) % ${#chars}))
        sleep 0.1
    done
}

# Clear the spinner line
spin_clear() {
    printf "\r\033[K"
}

# Print a table row
# Usage: table_row "Column1" "Column2" "Column3"
table_row() {
    printf "%-20s %-30s %s\n" "$@"
}

# JSON output mode (for scripting)
json_output() {
    echo "$1" | jq .
}
