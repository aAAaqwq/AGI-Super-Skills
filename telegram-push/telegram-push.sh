#!/bin/bash
# Telegram Push - 快速推送消息到指定群
# 用法: 
#   telegram-push.sh "消息内容"                    # 推送到默认群 (DailyNews)
#   telegram-push.sh "消息内容" -1001234567890    # 推送到指定群

set -e

TOKEN=$(pass tokens/telegram-newsrobot)
DEFAULT_CHAT_ID="-1003824568687"  # DailyNews

MESSAGE="$1"
CHAT_ID="${2:-$DEFAULT_CHAT_ID}"

if [ -z "$MESSAGE" ]; then
  echo "用法: telegram-push.sh \"消息内容\" [chat_id]"
  exit 1
fi

RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\": ${CHAT_ID}, \"text\": \"${MESSAGE}\"}")

if echo "$RESPONSE" | jq -e '.ok == true' > /dev/null 2>&1; then
  echo "✅ 推送成功"
  echo "$RESPONSE" | jq -r '.result.message_id'
else
  echo "❌ 推送失败"
  echo "$RESPONSE" | jq -r '.description // .error_description // "未知错误"'
  exit 1
fi
