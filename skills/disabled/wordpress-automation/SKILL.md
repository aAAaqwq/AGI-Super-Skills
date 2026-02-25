---
name: wordpress-automation
description: "Automate WordPress tasks via Rube MCP (Composio): posts, pages, media, categories, tags, and comments. Always search tools first for current schemas."
requires:
  mcp: [rube]
---

# WordPress Automation via Rube MCP

Automate WordPress operations through Composio's WordPress toolkit via Rube MCP.

## Prerequisites

- Rube MCP must be connected (RUBE_SEARCH_TOOLS available)
- Active WordPress connection via `RUBE_MANAGE_CONNECTIONS` with toolkit `wordpress`
- Always call `RUBE_SEARCH_TOOLS` first to get current tool schemas

## Setup

**Get Rube MCP**: Add `https://rube.app/mcp` as an MCP server in your client configuration.

1. Verify Rube MCP is available by confirming `RUBE_SEARCH_TOOLS` responds
2. Call `RUBE_MANAGE_CONNECTIONS` with toolkit `wordpress`
3. If connection is not ACTIVE, follow the returned auth link
4. Confirm connection status shows ACTIVE

## Core Workflows

### 1. Post Management
- Create, update, delete posts
- Set post status (draft, publish, schedule)
- Manage categories and tags
- Set featured images

### 2. Page Management
- Create and edit pages
- Manage page hierarchy (parent/child)
- Set page templates

### 3. Media Library
- Upload images and files
- List and search media
- Update media metadata

### 4. Taxonomy
- Create/manage categories
- Create/manage tags
- Assign taxonomies to posts

### 5. Comments
- List and moderate comments
- Reply to comments
- Approve/spam/trash comments

## Tool Discovery Pattern

```
RUBE_SEARCH_TOOLS query="wordpress" toolkit="wordpress"
```

## Important Notes

- WordPress.com and self-hosted WordPress may have different API capabilities
- Media uploads require appropriate file size limits
- Scheduled posts use the site's timezone setting
