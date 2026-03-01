# MCP API 完整参考

## 基础配置

| 配置项 | 值 |
|--------|-----|
| MCP 服务地址 | `http://localhost:18060/mcp` |
| Cookies 路径 | `~/.xiaohongshu/cookies.json` |
| 日志路径 | `~/.xiaohongshu/mcp.log` |

---

## 工具列表

### 1. check_login_status

检查登录状态。

**请求：**
```json
{
  "tool": "check_login_status",
  "params": {}
}
```

**响应：**
```json
{
  "logged_in": true,
  "user_id": "xxx",
  "username": "用户名"
}
```

---

### 2. search_feeds

搜索小红书内容。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |
| limit | number | 否 | 返回数量，默认 20 |

**请求：**
```json
{
  "tool": "search_feeds",
  "params": {
    "keyword": "OpenClaw",
    "limit": 10
  }
}
```

**响应：**
```json
{
  "feeds": [
    {
      "note_id": "xxx",
      "title": "帖子标题",
      "author": "作者名",
      "liked_count": 100,
      "xsec_token": "xxx"
    }
  ]
}
```

---

### 3. list_feeds

获取首页推荐列表。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| limit | number | 否 | 返回数量，默认 20 |

**请求：**
```json
{
  "tool": "list_feeds",
  "params": {
    "limit": 10
  }
}
```

---

### 4. get_feed_detail

获取帖子详情和评论。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| note_id | string | 是 | 帖子 ID |
| xsec_token | string | 是 | 安全 token |

**请求：**
```json
{
  "tool": "get_feed_detail",
  "params": {
    "note_id": "xxx",
    "xsec_token": "xxx"
  }
}
```

**响应：**
```json
{
  "title": "帖子标题",
  "content": "帖子正文",
  "author": {
    "user_id": "xxx",
    "nickname": "作者昵称"
  },
  "liked_count": 100,
  "collected_count": 50,
  "comment_count": 20,
  "shared_count": 10,
  "comments": [
    {
      "id": "xxx",
      "content": "评论内容",
      "author": "评论者"
    }
  ]
}
```

---

### 5. post_comment_to_feed

发表评论。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| note_id | string | 是 | 帖子 ID |
| xsec_token | string | 是 | 安全 token |
| content | string | 是 | 评论内容 |

**请求：**
```json
{
  "tool": "post_comment_to_feed",
  "params": {
    "note_id": "xxx",
    "xsec_token": "xxx",
    "content": "写得很棒！"
  }
}
```

---

### 6. reply_comment_in_feed

回复评论。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| note_id | string | 是 | 帖子 ID |
| comment_id | string | 是 | 评论 ID |
| content | string | 是 | 回复内容 |

---

### 7. user_profile

获取用户主页。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID |

**请求：**
```json
{
  "tool": "user_profile",
  "params": {
    "user_id": "xxx"
  }
}
```

**响应：**
```json
{
  "user_id": "xxx",
  "nickname": "用户昵称",
  "desc": "个人简介",
  "fans_count": 1000,
  "follow_count": 100,
  "liked_count": 5000,
  "notes": [
    {
      "note_id": "xxx",
      "title": "帖子标题"
    }
  ]
}
```

---

### 8. like_feed

点赞/取消点赞。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| note_id | string | 是 | 帖子 ID |
| xsec_token | string | 是 | 安全 token |
| like | boolean | 是 | true=点赞, false=取消 |

**请求：**
```json
{
  "tool": "like_feed",
  "params": {
    "note_id": "xxx",
    "xsec_token": "xxx",
    "like": true
  }
}
```

---

### 9. favorite_feed

收藏/取消收藏。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| note_id | string | 是 | 帖子 ID |
| xsec_token | string | 是 | 安全 token |
| favorite | boolean | 是 | true=收藏, false=取消 |

---

### 10. publish_content

发布图文笔记。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 标题（≤20字符） |
| content | string | 是 | 正文（≤1000字符） |
| images | array | 是 | 图片路径列表（最多18张） |
| tags | array | 否 | 标签列表 |

**请求：**
```json
{
  "tool": "publish_content",
  "params": {
    "title": "标题",
    "content": "正文内容",
    "images": ["/path/to/image1.jpg", "/path/to/image2.jpg"],
    "tags": ["标签1", "标签2"]
  }
}
```

**响应：**
```json
{
  "success": true,
  "note_id": "xxx",
  "url": "https://www.xiaohongshu.com/explore/xxx"
}
```

---

### 11. publish_with_video

发布视频笔记。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 标题（≤20字符） |
| content | string | 是 | 正文（≤1000字符） |
| video | string | 是 | 视频文件路径（≤15分钟） |
| cover | string | 否 | 封面图片路径 |
| tags | array | 否 | 标签列表 |

---

## 错误处理

### 常见错误码

| 错误码 | 说明 | 解决方法 |
|--------|------|----------|
| 401 | 未登录 | 重新获取 cookies |
| 429 | 请求频繁 | 降低请求频率 |
| 500 | 服务器错误 | 稍后重试 |

### 错误响应格式

```json
{
  "error": {
    "code": 401,
    "message": "未登录或登录已过期"
  }
}
```

---

## 调用示例

### cURL

```bash
curl -X POST http://localhost:18060/mcp \
  -H "Content-Type: application/json" \
  -d '{"tool": "check_login_status", "params": {}}'
```

### Python

```python
import requests

def call_mcp(tool, params=None):
    response = requests.post(
        "http://localhost:18060/mcp",
        json={"tool": tool, "params": params or {}}
    )
    return response.json()

# 使用示例
status = call_mcp("check_login_status")
feeds = call_mcp("search_feeds", {"keyword": "OpenClaw", "limit": 10})
```

### Bash (使用 jq)

```bash
#!/bin/bash
MCP_URL="http://localhost:18060/mcp"

mcp_call() {
    local tool=$1
    local params=$2
    curl -s -X POST "$MCP_URL" \
        -H "Content-Type: application/json" \
        -d "{\"tool\": \"$tool\", \"params\": $params}" | jq .
}

# 使用示例
mcp_call "check_login_status" "{}"
mcp_call "search_feeds" '{"keyword": "OpenClaw", "limit": 10}'
```