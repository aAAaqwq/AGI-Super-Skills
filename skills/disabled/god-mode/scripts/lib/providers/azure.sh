#!/usr/bin/env bash
# Azure DevOps provider for god-mode (STUB)
# Uses `az` CLI for authentication and API calls
#
# Status: Not yet implemented
# TODO: Implement for v0.2.0

# Check if az CLI is available and authenticated
azure_check_auth() {
    if ! command -v az &>/dev/null; then
        echo '{"available":false,"authenticated":false,"user":null,"message":"Azure CLI not installed"}'
        return 1
    fi

    if az account show &>/dev/null; then
        local user
        user=$(az account show --query user.name -o tsv 2>/dev/null || echo "")
        echo "{\"available\":true,\"authenticated\":true,\"user\":\"$user\",\"message\":\"Azure DevOps support coming soon\"}"
        return 0
    else
        echo '{"available":true,"authenticated":false,"user":null,"message":"Run: az login"}'
        return 1
    fi
}

# List accessible repositories (STUB)
azure_list_repos() {
    echo "[]"
}

# Fetch commits (STUB)
azure_fetch_commits() {
    echo "[]"
}

# Fetch pull requests (STUB)
azure_fetch_prs() {
    echo "[]"
}

# Fetch work items/issues (STUB)
azure_fetch_issues() {
    echo "[]"
}

# Get repository metadata (STUB)
azure_get_repo() {
    echo "{}"
}

# Normalize Azure DevOps repo identifier
# Input: "azure:org/project/repo" or "https://dev.azure.com/org/project/_git/repo"
# Output: "org/project/repo"
azure_normalize_repo() {
    local input="$1"

    # Remove azure: prefix
    input="${input#azure:}"

    # Remove Azure DevOps URL prefix
    input="${input#https://dev.azure.com/}"
    input="${input#https://}"

    # Remove _git path component
    input="${input/\/_git\//\/}"

    echo "$input"
}
