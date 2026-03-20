# 知识星球 API 详细文档

## Base URL

`https://api.zsxq.com`

## 认证

所有API请求需携带Cookie:
```
Cookie: zsxq_access_token={your_token}
```

Token获取方式：
1. 浏览器打开 https://wx.zsxq.com
2. 微信扫码登录
3. F12 → Application → Cookies → 复制 `zsxq_access_token`

## 接口列表

### 1. 获取用户加入的星球列表

```
GET /v2/groups
```

Response:
```json
{
  "succeeded": true,
  "resp_data": {
    "group_list": [
      {
        "group_id": "12345678901234",
        "group_name": "我的星球",
        "type": "pay|free",
        "member_count": 1000
      }
    ]
  }
}
```

### 2. 获取话题列表

```
GET /v1.10/groups/{group_id}/topics?scope=all&count=20&end_time={timestamp}
```

scope参数:
- `all` — 全部
- `digests` — 精华
- `questions` — 问答
- `tasks` — 作业

### 3. 创建话题

```
POST /v2/groups/{group_id}/topics
Content-Type: application/json
```

Body:
```json
{
  "req_data": {
    "topic": {
      "type": "talk",
      "text": "内容文字（支持有限Markdown）\n#标签1 #标签2",
      "title": "可选标题",
      "image_count": 1,
      "images": [
        {"file_size": 12345, "width": 800, "height": 600}
      ]
    }
  }
}
```

type类型: `talk` | `q&a` | `task`

### 4. 上传图片

```
POST /v2/files/{group_id}/images
Content-Type: multipart/form-data

file: (binary image data)
```

Response:
```json
{
  "resp_data": {
    "upload_key": "xxx",
    "width": 800,
    "height": 600,
    "file_size": 12345
  }
}
```

### 5. 上传文件

```
POST /v2/files/{group_id}/files
Content-Type: multipart/form-data

file: (binary file data)
```

### 6. 获取文件下载链接

```
GET /v2/files/{file_id}/download_url
```

⚠️ 注意: 频繁调用此接口会被监控，可能导致封号。

### 7. 设置精华

```
POST /v2/topics/{topic_id}/digest
```

### 8. 获取评论

```
GET /v1.10/topics/{topic_id}/comments?count=20
```

### 9. 评论/回复

```
POST /v1.10/topics/{topic_id}/comments
```

## Rate Limiting

- 未公开具体限制
- 短时间大量请求会触发429
- 建议间隔 ≥ 2秒/请求
- 文件下载接口监控更严格

## 已知限制

- 长文章(100K字符)只能通过网页端发布，无API
- 图片需先上传获取upload_key，再在创建话题时引用
- 标签通过text内容中的 #标签 格式添加
- 话题编辑功能API有限，复杂编辑建议用浏览器
