#!/bin/bash

# Tavily API 调用脚本
# API Key 从 pass 获取

set -e

API_KEY=$(pass show api/tavily 2>/dev/null | head -1)
BASE_URL="https://api.tavily.com"

if [ -z "$API_KEY" ]; then
    echo "错误: 无法获取 Tavily API Key"
    echo "请确保已存储: pass insert api/tavily"
    exit 1
fi

# 搜索函数
search() {
    local query="$1"
    local max_results="${2:-5}"
    local search_depth="basic"
    
    # 检查是否有 --deep 参数
    if [ "$3" == "--deep" ] || [ "$2" == "--deep" ]; then
        search_depth="advanced"
        if [ "$2" == "--deep" ]; then
            max_results="${3:-5}"
        fi
    fi
    
    echo "正在搜索: $query"
    echo "深度: $search_depth"
    echo "结果数: $max_results"
    echo "---"
    
    curl -s -X POST "${BASE_URL}/search" \
        -H "Authorization: Bearer ${API_KEY}" \
        -H "Content-Type: application/json" \
        -d "{
            \"query\": \"$query\",
            \"max_results\": $max_results,
            \"search_depth\": \"$search_depth\",
            \"include_answer\": true,
            \"include_raw_content\": false
        }" | jq '{
            answer: .answer,
            results: [.results[] | {
                title: .title,
                url: .url,
                content: .content,
                score: .score
            }]
        }'
}

# 搜索并提取内容
extract() {
    local query="$1"
    local max_results="${2:-5}"
    
    echo "正在搜索并提取: $query"
    echo "结果数: $max_results"
    echo "---"
    
    curl -s -X POST "${BASE_URL}/search" \
        -H "Authorization: Bearer ${API_KEY}" \
        -H "Content-Type: application/json" \
        -d "{
            \"query\": \"$query\",
            \"max_results\": $max_results,
            \"search_depth\": \"advanced\",
            \"include_answer\": true,
            \"include_raw_content\": true
        }" | jq '{
            answer: .answer,
            results: [.results[] | {
                title: .title,
                url: .url,
                content: .content,
                raw_content: .raw_content[0:500],
                score: .score
            }]
        }'
}

# 帮助信息
help() {
    echo "Tavily API 调用脚本"
    echo ""
    echo "用法:"
    echo "  $0 search <query> [max_results]     基础搜索"
    echo "  $0 search <query> --deep            深度搜索"
    echo "  $0 extract <query> [max_results]    搜索并提取内容"
    echo ""
    echo "示例:"
    echo "  $0 search \"AI news\" 5"
    echo "  $0 search \"Bitcoin price\" --deep"
    echo "  $0 extract \"Polymarket prediction\" 3"
}

# 主入口
case "$1" in
    search)
        search "$2" "$3" "$4"
        ;;
    extract)
        extract "$2" "$3"
        ;;
    *)
        help
        ;;
esac
