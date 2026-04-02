#!/usr/bin/env bash
# qingyun-common.sh — 青云聚合API 公共函数库
# 所有 qingyun-api 脚本 source 此文件

set -euo pipefail

QINGYUN_BASE_URL="${QINGYUN_BASE_URL:-https://api.qingyuntop.top}"
QINGYUN_API_KEY="${QINGYUN_API_KEY:-}"

if [[ -z "$QINGYUN_API_KEY" ]]; then
  echo "ERROR: QINGYUN_API_KEY not set. Run: export QINGYUN_API_KEY='<your-api-key>'" >&2
  exit 1
fi

# 通用 HTTP 请求
# Usage: qy_request METHOD PATH [BODY_JSON]
qy_request() {
  local method="$1" path="$2" body="${3:-}"
  local url="${QINGYUN_BASE_URL}${path}"
  
  local args=(-s -w "\n%{http_code}" -X "$method" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -H "Authorization: Bearer ${QINGYUN_API_KEY}")
  
  if [[ -n "$body" ]]; then
    args+=(-d "$body")
  fi
  
  local response
  response=$(curl --max-time 60 "${args[@]}" "$url")
  local http_code
  http_code=$(echo "$response" | tail -1)
  local body_content
  body_content=$(echo "$response" | sed '$d')
  
  if [[ "$http_code" -ge 400 ]]; then
    echo "ERROR: HTTP $http_code" >&2
    echo "$body_content" >&2
    return 1
  fi
  
  echo "$body_content"
}

# 任务轮询 (用于异步 API)
# Usage: qy_poll METHOD PATH INTERVAL MAX_WAIT [KEY]
# KEY 是 JSON 中状态字段名，默认 "status"
# 完成状态: completed / succeed
qy_poll() {
  local method="$1" path="$2" interval="${3:-10}" max_wait="${4:-300}" status_key="${5:-status}"
  local elapsed=0
  
  while [[ $elapsed -lt $max_wait ]]; do
    local result
    result=$(qy_request "$method" "$path")
    local status
    status=$(echo "$result" | jq -r ".$status_key" 2>/dev/null || echo "unknown")
    
    case "$status" in
      completed|succeed|succeeded|success)
        echo "$result"
        return 0
        ;;
      failed|error)
        echo "ERROR: Task failed" >&2
        echo "$result" >&2
        return 1
        ;;
      processing|running|pending)
        echo "Status: $status (elapsed: ${elapsed}s)" >&2
        ;;
      *)
        echo "Status: $status (elapsed: ${elapsed}s)" >&2
        ;;
    esac
    
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done
  
  echo "ERROR: Timeout after ${max_wait}s" >&2
  return 1
}

# 保存 URL 到文件
# Usage: qy_download URL OUTPUT_FILE
qy_download() {
  local url="$1" output="$2"
  curl -sL --max-time 120 -o "$output" "$url"
  echo "Downloaded: $output ($(du -h "$output" | cut -f1))"
}

# 输出 JSON 格式化
qy_json() {
  echo "$1" | jq '.' 2>/dev/null || echo "$1"
}

# Gemini 原生格式请求 (key 在 query param)
# Usage: qy_gemini PATH [BODY_JSON]
qy_gemini() {
  local path="$1" body="${2:-}"
  local url="${QINGYUN_BASE_URL}${path}?key=${QINGYUN_API_KEY}"
  
  local args=(-s -w "\n%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json")
  
  if [[ -n "$body" ]]; then
    args+=(-d "$body")
  fi
  
  local response
  response=$(curl --max-time 120 "${args[@]}" "$url")
  local http_code
  http_code=$(echo "$response" | tail -1)
  local body_content
  body_content=$(echo "$response" | sed '$d')
  
  if [[ "$http_code" -ge 400 ]]; then
    echo "ERROR: HTTP $http_code" >&2
    echo "$body_content" >&2
    return 1
  fi
  
  echo "$body_content"
}

# 解析 Gemini base64 音频并保存
# Usage: qy_save_gemini_audio JSON_RESULT OUTPUT_FILE
qy_save_gemini_audio() {
  local json="$1" output="$2"
  local b64data
  b64data=$(echo "$json" | jq -r '.candidates[0].content.parts[] | select(.inlineData) | .inlineData.data' 2>/dev/null | head -1)
  local mime
  mime=$(echo "$json" | jq -r '.candidates[0].content.parts[] | select(.inlineData) | .inlineData.mimeType' 2>/dev/null | head -1)
  
  if [[ -z "$b64data" || "$b64data" == "null" ]]; then
    echo "ERROR: No audio data in response" >&2
    echo "$json" >&2
    return 1
  fi
  
  # 根据 MIME 确定扩展名
  local ext="mp3"
  case "$mime" in
    audio/wav|audio/wave) ext="wav" ;;
    audio/mp3) ext="mp3" ;;
    audio/opus) ext="opus" ;;
    audio/aac) ext="aac" ;;
    audio/*) ext="${mime#audio/}" ;;
  esac
  
  local final_output="${output%.*}.${ext}"
  echo "$b64data" | base64 -d > "$final_output"
  echo "Saved: $final_output (mime: $mime, size: $(du -h "$final_output" | cut -f1))"
}

echo "QingYun API v1.0 — Base: ${QINGYUN_BASE_URL}" >&2
