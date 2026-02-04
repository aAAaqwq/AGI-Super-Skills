#!/bin/bash
# 飞书快捷发送脚本（多租户）
# 
# 用法:
#   ./feishu-send.sh "消息"                    # 发送到汉兴默认群
#   ./feishu-send.sh <chat_id> "消息"          # 发送到指定群
#   ./feishu-send.sh --personal "消息"         # 发送到个人默认群
#   ./feishu-send.sh --personal <chat_id> "消息"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 默认配置
TENANT=""
CHAT_ID=""
MESSAGE=""

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --personal|-p)
            TENANT="personal"
            shift
            ;;
        --hanxing|-h)
            TENANT="hanxing"
            shift
            ;;
        *)
            if [[ -z "$MESSAGE" ]]; then
                # 检查是否是 chat_id (以 oc_ 开头)
                if [[ "$1" == oc_* ]]; then
                    CHAT_ID="$1"
                else
                    MESSAGE="$1"
                fi
            else
                MESSAGE="$MESSAGE $1"
            fi
            shift
            ;;
    esac
done

if [[ -z "$MESSAGE" ]]; then
    echo "用法: $0 [--personal|--hanxing] [chat_id] <消息>"
    echo ""
    echo "示例:"
    echo "  $0 \"Hello\"                    # 发送到汉兴技术开发群"
    echo "  $0 --personal \"Hello\"         # 发送到个人知识云文档群"
    echo "  $0 oc_xxx \"Hello\"             # 发送到指定群"
    exit 1
fi

# 构建命令
CMD="python3 $SCRIPT_DIR/feishu_api.py"
if [[ -n "$TENANT" ]]; then
    CMD="$CMD --tenant $TENANT"
fi

if [[ -n "$CHAT_ID" ]]; then
    $CMD send "$CHAT_ID" "$MESSAGE"
else
    # 使用默认群组
    $CMD send-default "$MESSAGE"
fi
