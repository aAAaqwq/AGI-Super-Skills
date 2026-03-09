#!/bin/bash
# md2feishu.sh - 将 Markdown 文件导入飞书云文档
# 用法: ./md2feishu.sh /path/to/document.md [chat_id]
# 如果提供 chat_id，会自动发送文档链接到群
# 
# 标准流程：
# 1. 上传到云盘
# 2. 导入为云文档
# 3. 设置权限（组织内可编辑）
# 4. 发送到群（可选）

set -e

MD_FILE="$1"
CHAT_ID="$2"

if [ -z "$MD_FILE" ]; then
    echo "用法: $0 <markdown_file> [chat_id]"
    exit 1
fi

if [ ! -f "$MD_FILE" ]; then
    echo "错误: 文件不存在: $MD_FILE"
    exit 1
fi

# 从 pass 获取凭证（汉兴企业）
APP_ID="YOUR_APP_ID"
APP_SECRET=$(pass show api/feishu-hanxing 2>/dev/null || echo "")

if [ -z "$APP_SECRET" ]; then
    echo "错误: 无法获取飞书 App Secret，请检查 pass api/feishu-hanxing"
    exit 1
fi

echo "📤 正在上传: $MD_FILE"

# 1. 获取 access_token
TOKEN=$(curl -s -X POST 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' \
  -H 'Content-Type: application/json' \
  -d '{"app_id":"'"$APP_ID"'","app_secret":"'"$APP_SECRET"'"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('tenant_access_token',''))")

if [ -z "$TOKEN" ]; then
    echo "错误: 获取 access_token 失败"
    exit 1
fi

# 2. 上传文件到飞书云盘
FILE_NAME=$(basename "$MD_FILE")
FILE_SIZE=$(stat -c%s "$MD_FILE")

echo "📁 上传文件到云盘..."
UPLOAD_RESULT=$(curl -s -X POST 'https://open.feishu.cn/open-apis/drive/v1/files/upload_all' \
  -H "Authorization: Bearer $TOKEN" \
  -F "file_name=$FILE_NAME" \
  -F "parent_type=explorer" \
  -F "parent_node=" \
  -F "size=$FILE_SIZE" \
  -F "file=@$MD_FILE")

FILE_TOKEN=$(echo "$UPLOAD_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('file_token',''))")

if [ -z "$FILE_TOKEN" ]; then
    echo "错误: 上传文件失败"
    echo "$UPLOAD_RESULT"
    exit 1
fi

echo "✅ 文件上传成功: $FILE_TOKEN"

# 3. 导入为飞书云文档
echo "📝 导入为云文档..."
IMPORT_RESULT=$(curl -s -X POST 'https://open.feishu.cn/open-apis/drive/v1/import_tasks' \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_extension": "md",
    "file_token": "'"$FILE_TOKEN"'",
    "type": "docx",
    "point": {"mount_type": 1, "mount_key": ""}
  }')

TICKET=$(echo "$IMPORT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('ticket',''))")

if [ -z "$TICKET" ]; then
    echo "错误: 创建导入任务失败"
    echo "$IMPORT_RESULT"
    exit 1
fi

echo "⏳ 等待导入完成..."
sleep 2

# 4. 获取导入结果
TASK_RESULT=$(curl -s -X GET "https://open.feishu.cn/open-apis/drive/v1/import_tasks/$TICKET" \
  -H "Authorization: Bearer $TOKEN")

DOC_TOKEN=$(echo "$TASK_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('result',{}).get('token',''))")
DOC_URL=$(echo "$TASK_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('result',{}).get('url',''))")
JOB_STATUS=$(echo "$TASK_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('result',{}).get('job_status',1))")

if [ "$JOB_STATUS" != "0" ] || [ -z "$DOC_URL" ]; then
    echo "错误: 导入失败"
    echo "$TASK_RESULT"
    exit 1
fi

echo "✅ 导入成功！"

# 5. 设置权限：组织内获得链接的人可编辑
echo "🔐 设置文档权限..."
curl -s -X PATCH "https://open.feishu.cn/open-apis/drive/v1/permissions/$DOC_TOKEN/public?type=docx" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "external_access_entity": "open",
    "security_entity": "anyone_can_view",
    "comment_entity": "anyone_can_view",
    "share_entity": "anyone",
    "link_share_entity": "tenant_editable"
  }' > /dev/null

echo "✅ 权限已设置：组织内可编辑"

echo ""
echo "📄 文档链接: $DOC_URL"

# 6. 如果提供了 chat_id，发送到群
if [ -n "$CHAT_ID" ]; then
    echo ""
    echo "📤 发送到群组: $CHAT_ID"
    
    curl -s -X POST "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "receive_id": "'"$CHAT_ID"'",
        "msg_type": "text",
        "content": "{\"text\":\"📄 文档已上传（组织内可编辑）：\\n\\n'"$DOC_URL"'\"}"
      }' > /dev/null
    
    echo "✅ 已发送到群组"
fi

echo ""
echo "🎉 完成！"
