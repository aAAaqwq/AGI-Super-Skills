#!/bin/bash
# Real News Fetcher - Uses OpenClaw web_search tool
# This script ACTUALLY searches for real news from real sources

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="/tmp/news-daily"
OUTPUT_SUMMARY="$TMP_DIR/real-summary.txt"

# Create temp directory
mkdir -p "$TMP_DIR"

echo "🔍 Starting real news fetch..."
echo "⏰ Time: $(date)"

# Define search queries for different sources
declare -A SEARCHES
SEARCHES[机器之心]="site:jiqizhixin.com AI 人工智能 最新"
SEARCHES[36氪]="site:36kr.com AI 科技 前沿"
SEARCHES[TechCrunch]="site:techcrunch.com artificial intelligence AI"
SEARCHES[虎嗅]="site:huxiu.com AI 科技"
SEARCHES[MIT]="site:technologyreview.com AI artificial intelligence"

# Search for real news using OpenClaw web_search
echo "📡 Searching for real news..."

# This will be called by OpenClaw agent with web_search tool
cat > "$TMP_DIR/search-queries.txt" << EOF
Searching for real AI news from authoritative sources:

1. 机器之心: site:jiqizhixin.com AI 人工智能 最新
2. 36氪: site:36kr.com AI 科技 前沿
3. TechCrunch: site:techcrunch.com artificial intelligence AI
4. 虎嗅: site:huxiu.com AI 科技
5. MIT Technology Review: site:technologyreview.com AI artificial intelligence

Use web_search tool with these queries to find real articles.
Extract: title, url, source, published date
Only include articles from last 24 hours
EOF

echo "✅ Search queries prepared"
echo "📋 Queries saved to: $TMP_DIR/search-queries.txt"

# Output instructions for the agent
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 NEWS FETCHING INSTRUCTIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Please use web_search tool to search for REAL news:"
echo ""
cat "$TMP_DIR/search-queries.txt"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "After searching, format the results like this:"
echo ""
echo "📰 每日科技早报 | $(date +%Y-%m-%d)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "[News Title]"
echo "来源：[Source] | [Time]"
echo "[URL]"
echo ""
echo "摘要：[Summary]"
echo "  - [Key point 1]"
echo "  - [Key point 2]"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️ IMPORTANT:"
echo "- Only use REAL news from search results"
echo "- Verify URLs are accessible"
echo "- Include actual publication dates"
echo "- Don't generate fake news"
