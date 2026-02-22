#!/bin/bash

# Firecrawl API 调用脚本
# API Key 从 pass 获取

set -e

API_KEY=$(pass show api/firecrawl 2>/dev/null | head -1)
BASE_URL="https://api.firecrawl.dev/v1"

if [ -z "$API_KEY" ]; then
    echo "错误: 无法获取 Firecrawl API Key"
    echo "请确保已存储: pass insert api/firecrawl"
    exit 1
fi

# 通用请求函数
firecrawl_request() {
    local endpoint="$1"
    local data="$2"
    
    curl -s -X POST "${BASE_URL}${endpoint}" \
        -H "Authorization: Bearer ${API_KEY}" \
        -H "Content-Type: application/json" \
        -d "$data"
}

# 抓取单个网页
scrape() {
    local url="$1"
    local format="${2:-markdown}"
    
    echo "正在抓取: $url"
    echo "格式: $format"
    echo "---"
    
    firecrawl_request "/scrape" "{
        \"url\": \"$url\",
        \"formats\": [\"$format\"],
        \"onlyMainContent\": true
    }" | jq -r '.data.content // .data.markdown // .'
}

# 提取结构化数据
extract() {
    local url="$1"
    local schema="$2"
    
    echo "正在提取: $url"
    echo "Schema: $schema"
    echo "---"
    
    firecrawl_request "/scrape" "{
        \"url\": \"$url\",
        \"formats\": [\"extract\"],
        \"extract\": {
            \"schema\": $schema
        }
    }" | jq '.data.extract // .'
}

# 批量爬取网站
crawl() {
    local url="$1"
    local max_pages="${2:-10}"
    
    echo "正在爬取: $url"
    echo "最大页数: $max_pages"
    echo "---"
    
    # 先发起爬取请求
    local job_id=$(firecrawl_request "/crawl" "{
        \"url\": \"$url\",
        \"maxDepth\": 2,
        \"limit\": $max_pages,
        \"scrapeOptions\": {
            \"formats\": [\"markdown\"],
            \"onlyMainContent\": true
        }
    }" | jq -r '.id // .')
    
    if [ "$job_id" == "null" ] || [ -z "$job_id" ]; then
        echo "爬取失败"
        exit 1
    fi
    
    echo "爬取任务已创建: $job_id"
    echo "等待完成..."
    
    # 轮询任务状态
    local status="scraping"
    local attempts=0
    local max_attempts=60
    
    while [ "$status" != "completed" ] && [ $attempts -lt $max_attempts ]; do
        sleep 2
        status=$(curl -s "${BASE_URL}/crawl/${job_id}" \
            -H "Authorization: Bearer ${API_KEY}" | jq -r '.status // "unknown"')
        echo "状态: $status"
        attempts=$((attempts + 1))
    done
    
    # 获取结果
    if [ "$status" == "completed" ]; then
        curl -s "${BASE_URL}/crawl/${job_id}" \
            -H "Authorization: Bearer ${API_KEY}" | jq '.data // .'
    else
        echo "爬取超时"
        exit 1
    fi
}

# 搜索并抓取
search() {
    local query="$1"
    local limit="${2:-5}"
    
    echo "正在搜索: $query"
    echo "限制: $limit"
    echo "---"
    
    firecrawl_request "/search" "{
        \"query\": \"$query\",
        \"limit\": $limit,
        \"scrapeOptions\": {
            \"formats\": [\"markdown\"],
            \"onlyMainContent\": true
        }
    }" | jq '.data // .'
}

# 帮助信息
help() {
    echo "Firecrawl API 调用脚本"
    echo ""
    echo "用法:"
    echo "  $0 scrape <url> [format]     抓取单个网页"
    echo "  $0 extract <url> <schema>    提取结构化数据"
    echo "  $0 crawl <url> [max_pages]   批量爬取网站"
    echo "  $0 search <query> [limit]    搜索并抓取"
    echo ""
    echo "示例:"
    echo "  $0 scrape https://example.com"
    echo "  $0 extract https://example.com '{\"title\": \"string\"}'"
    echo "  $0 crawl https://example.com 10"
    echo "  $0 search \"AI news\" 5"
}

# 主入口
case "$1" in
    scrape)
        scrape "$2" "$3"
        ;;
    extract)
        extract "$2" "$3"
        ;;
    crawl)
        crawl "$2" "$3"
        ;;
    search)
        search "$2" "$3"
        ;;
    *)
        help
        ;;
esac
