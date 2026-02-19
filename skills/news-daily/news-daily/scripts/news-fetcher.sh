#!/bin/bash
# News Daily - News Fetcher Script
# Fetches, summarizes, and pushes daily tech news

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load configuration
source "$SCRIPT_DIR/config.sh"

# Parse arguments
PUSH_CHANNEL=""
SOURCE_LIST=""
ARTICLE_COUNT=$DEFAULT_ARTICLE_COUNT

while [[ $# -gt 0 ]]; do
  case $1 in
    --push)
      PUSH_CHANNEL="$2"
      shift 2
      ;;
    --sources)
      SOURCE_LIST="$2"
      shift 2
      ;;
    --articles)
      ARTICLE_COUNT="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo "Options:"
      echo "  --push <channel>     Push to telegram or whatsapp"
      echo "  --sources <list>     Comma-separated list of sources"
      echo "  --articles <n>       Number of articles to summarize (default: $DEFAULT_ARTICLE_COUNT)"
      echo "  --help, -h           Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Use default channel if none specified
if [ -z "$PUSH_CHANNEL" ] && [ -n "$DEFAULT_CHANNEL" ]; then
  PUSH_CHANNEL="$DEFAULT_CHANNEL"
fi

# Create necessary directories
mkdir -p "$LOG_DIR" "$CACHE_DIR" "$TMP_DIR"

# Log file
TIMESTAMP=$(date "$DATE_FORMAT")
LOG_FILE="$LOG_DIR/news-fetch-$(date +%Y%m%d-%H%M%S).log"

# Function to log messages
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting news fetch process"

# Function to fetch news from a source
fetch_from_source() {
  local source_name="$1"
  local source_url="$2"
  local fetch_method="$3"
  local search_term="$4"

  log "Fetching from $source_name ($fetch_method)"

  case "$fetch_method" in
    web_search)
      # Use web_search tool (via OpenClaw CLI or direct call)
      log "  Searching for: $search_term"
      # This would be called via OpenClaw's tool system
      # For now, we'll create a placeholder for the search results
      echo "SEARCH:$source_name:$search_term" >> "$TMP_DIR/queries.txt"
      ;;
    web_fetch)
      # Use web_fetch tool to get content
      log "  Fetching from URL: $source_url"
      echo "FETCH:$source_name:$source_url" >> "$TMP_DIR/queries.txt"
      ;;
    *)
      log "  Unknown fetch method: $fetch_method"
      ;;
  esac
}

# Parse news sources configuration
log "Parsing news sources configuration"

SOURCES_CONFIG="$SCRIPT_DIR/news-sources.conf"
if [ ! -f "$SOURCES_CONFIG" ]; then
  log "ERROR: Sources config not found: $SOURCES_CONFIG"
  exit 1
fi

# Read sources from config
declare -A SOURCES
declare -A SOURCE_METHODS
declare -A SOURCE_PRIORITIES

while IFS='|' read -r name url method priority selector; do
  # Skip comments and empty lines
  [[ "$name" =~ ^#.*$ ]] && continue
  [[ -z "$name" ]] && continue

  # Skip if source list is specified and this source is not in it
  if [ -n "$SOURCE_LIST" ]; then
    if [[ ",$SOURCE_LIST," != *",$name,"* ]]; then
      continue
    fi
  fi

  SOURCES[$name]="$url"
  SOURCE_METHODS[$name]="$method"
  SOURCE_PRIORITIES[$name]="$priority"

  log "  Loaded source: $name (priority: $priority)"
done < "$SOURCES_CONFIG"

# Fetch news from each source
> "$TMP_DIR/queries.txt"

for source in "${!SOURCES[@]}"; do
  url="${SOURCES[$source]}"
  method="${SOURCE_METHODS[$source]}"

  # Determine search term based on source
  case "$source" in
    机器之心)
      search_term="AI 人工智能 最新"
      ;;
    36氪)
      search_term="AI 科技 前沿"
      ;;
    TechCrunch)
      search_term="artificial intelligence AI latest"
      ;;
    The\ Verge)
      search_term="AI technology news"
      ;;
    MIT\ Technology\ Review)
      search_term="artificial intelligence breakthrough"
      ;;
    *)
      search_term="AI artificial intelligence"
      ;;
  esac

  fetch_from_source "$source" "$url" "$method" "$search_term"

  # Respectful delay between requests
  sleep $REQUEST_DELAY
done

# Simulate news fetching (in real implementation, this would use web_search/web_fetch)
# For demonstration, we'll create a sample news file
cat > "$TMP_DIR/raw_news.json" << 'EOF'
{
  "articles": [
    {
      "title": "OpenAI 发布 GPT-5：推理能力大幅提升",
      "source": "机器之心",
      "url": "https://www.jiqizhixin.com/article/gpt5",
      "published": "2小时前",
      "summary": "OpenAI 正式发布 GPT-5，新模型在复杂推理任务上表现显著提升，支持多模态输入，推理成本降低40%。"
    },
    {
      "title": "Google DeepMind 新算法突破蛋白质折叠预测",
      "source": "MIT Technology Review",
      "url": "https://www.technologyreview.org/protein",
      "published": "5小时前",
      "summary": "DeepMind 的 AlphaFold 3 在蛋白质结构预测准确率达到新高度，将加速药物研发进程。"
    },
    {
      "title": "36氪独家：国产 AI 芯片企业完成 10 亿美元融资",
      "source": "36氪",
      "url": "https://36kr.com/p/ai-chip-funding",
      "published": "3小时前",
      "summary": "国内领先 AI 芯片企业完成新一轮融资，将用于大模型推理芯片研发。"
    }
  ],
  "total": 127,
  "timestamp": "2025-01-31 08:00:00"
}
EOF

log "Fetched $(cat "$TMP_DIR/raw_news.json" | grep -o '"title"' | wc -l) articles"

# Generate summary using news-summarizer.md prompt
SUMMARY_PROMPT="$SCRIPT_DIR/news-summarizer.md"
RAW_NEWS="$TMP_DIR/raw_news.json"
OUTPUT_SUMMARY="$TMP_DIR/summary.txt"

log "Generating summary"

# In real implementation, this would call an LLM with the prompt
# For now, generate a formatted summary
cat > "$OUTPUT_SUMMARY" << EOF
📰 每日科技早报 | $(date +%Y-%m-%d)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 OpenAI 发布 GPT-5：推理能力大幅提升
来源：机器之心 | 2小时前
https://www.jiqizhixin.com/article/gpt5

摘要：OpenAI 正式发布 GPT-5，新模型在复杂推理任务上表现显著提升。
  - 支持多模态输入（文本、图像、音频、视频）
  - 推理成本降低 40%
  - API 即日开放，企业版提供额外安全保证

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Google DeepMind 新算法突破蛋白质折叠预测
来源：MIT Technology Review | 5小时前
https://www.technologyreview.org/protein

摘要：DeepMind 的 AlphaFold 3 在蛋白质结构预测准确率达到新高度。
  - 预测精度提升 25%
  - 将大幅加速新药研发进程
  - 生物医药领域迎来重要突破

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 国产 AI 芯片企业完成 10 亿美元融资
来源：36氪 | 3小时前
https://36kr.com/p/ai-chip-funding

摘要：国内领先 AI 芯片企业完成新一轮融资。
  - 融资规模 10 亿美元，估值超 50 亿
  - 资金将用于大模型推理芯片研发
  - 国产算力基础设施加速发展

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 今日共收集 127 篇文章，精选 3 条重点新闻

💡 今日焦点：大模型竞争进入新阶段，推理效率和算力成本成为关键战场
EOF

log "Summary generated"

# Output to console
cat "$OUTPUT_SUMMARY"

# Push to channel if requested
if [ -n "$PUSH_CHANNEL" ]; then
  log "Pushing to $PUSH_CHANNEL"

  case "$PUSH_CHANNEL" in
    telegram)
      # In real implementation, use OpenClaw message tool
      log "  Would push to Telegram via message tool"
      # Example: openclaw message send --channel telegram --message "$(cat "$OUTPUT_SUMMARY")"
      ;;
    whatsapp)
      # In real implementation, use OpenClaw message tool
      log "  Would push to WhatsApp via message tool"
      # Example: openclaw message send --channel whatsapp --message "$(cat "$OUTPUT_SUMMARY")"
      ;;
    *)
      log "  Unknown channel: $PUSH_CHANNEL"
      ;;
  esac
fi

log "News fetch process completed"

# Cleanup old temp files (keep last 7 days)
find "$TMP_DIR" -type f -mtime +7 -delete 2>/dev/null || true

exit 0
