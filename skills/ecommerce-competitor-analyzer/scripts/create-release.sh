#!/bin/bash

# GitHub Release 创建脚本
# 需要先创建 GitHub Personal Access Token

TOKEN="YOUR_GITHUB_TOKEN_HERE"
REPO="buluslan/ecommerce-competitor-analyzer"
TAG="v1.0.0"
TITLE="🚀 E-commerce Competitor Analyzer v1.0.0"

# 读取 Release Notes
RELEASE_BODY=$(cat RELEASE_NOTES.md)

# 创建 Release
curl -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$REPO/releases \
  -d "{
    \"tag_name\": \"$TAG\",
    \"target_commitish\": \"main\",
    \"name\": \"$TITLE\",
    \"body\": $(echo "$RELEASE_BODY" | jq -Rs .),
    \"draft\": false,
    \"prerelease\": false
  }"

echo "✅ Release created: https://github.com/$REPO/releases/tag/$TAG"
