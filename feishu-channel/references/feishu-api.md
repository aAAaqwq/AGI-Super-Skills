# 飞书 API 参考

## 认证

### 获取 tenant_access_token

```bash
curl -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": "cli_xxx",
    "app_secret": "xxx"
  }'
```

响应：
```json
{
  "code": 0,
  "msg": "success",
  "tenant_access_token": "t-xxx",
  "expire": 7200
}
```

## 消息 API

### 发送消息

```bash
POST https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id
Authorization: Bearer {tenant_access_token}
Content-Type: application/json

{
  "receive_id": "ou_xxx",
  "msg_type": "text",
  "content": "{\"text\":\"Hello!\"}"
}
```

#### receive_id_type 类型

| 类型 | 说明 |
|------|------|
| `open_id` | 用户 open_id |
| `user_id` | 用户 user_id |
| `union_id` | 用户 union_id |
| `email` | 用户邮箱 |
| `chat_id` | 群聊 chat_id |

### 回复消息

```bash
POST https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply
Authorization: Bearer {tenant_access_token}
Content-Type: application/json

{
  "msg_type": "text",
  "content": "{\"text\":\"收到！\"}"
}
```

### 获取消息

```bash
GET https://open.feishu.cn/open-apis/im/v1/messages/{message_id}
Authorization: Bearer {tenant_access_token}
```

## 消息类型

### 文本消息 (text)

```json
{
  "msg_type": "text",
  "content": "{\"text\":\"Hello World\"}"
}
```

支持 @ 用户：
```json
{
  "text": "<at user_id=\"ou_xxx\">张三</at> 你好"
}
```

### 富文本消息 (post)

```json
{
  "msg_type": "post",
  "content": "{\"zh_cn\":{\"title\":\"标题\",\"content\":[[{\"tag\":\"text\",\"text\":\"内容\"}]]}}"
}
```

富文本元素：
- `text` - 文本
- `a` - 链接
- `at` - @用户
- `img` - 图片

### 图片消息 (image)

```json
{
  "msg_type": "image",
  "content": "{\"image_key\":\"img_xxx\"}"
}
```

需要先上传图片获取 image_key。

### 卡片消息 (interactive)

```json
{
  "msg_type": "interactive",
  "content": "{\"config\":{\"wide_screen_mode\":true},\"header\":{\"title\":{\"tag\":\"plain_text\",\"content\":\"标题\"}},\"elements\":[{\"tag\":\"div\",\"text\":{\"tag\":\"plain_text\",\"content\":\"内容\"}}]}"
}
```

## 卡片消息详解

### 基本结构

```json
{
  "config": {
    "wide_screen_mode": true,
    "enable_forward": true
  },
  "header": {
    "title": {
      "tag": "plain_text",
      "content": "卡片标题"
    },
    "template": "blue"
  },
  "elements": []
}
```

### header.template 颜色

- `blue` - 蓝色
- `wathet` - 浅蓝
- `turquoise` - 青色
- `green` - 绿色
- `yellow` - 黄色
- `orange` - 橙色
- `red` - 红色
- `carmine` - 深红
- `violet` - 紫色
- `purple` - 深紫
- `indigo` - 靛蓝
- `grey` - 灰色

### 元素类型

#### div - 内容块

```json
{
  "tag": "div",
  "text": {
    "tag": "lark_md",
    "content": "**粗体** _斜体_ [链接](https://example.com)"
  }
}
```

#### hr - 分割线

```json
{
  "tag": "hr"
}
```

#### action - 按钮组

```json
{
  "tag": "action",
  "actions": [
    {
      "tag": "button",
      "text": {
        "tag": "plain_text",
        "content": "确认"
      },
      "type": "primary",
      "value": {
        "key": "value"
      }
    }
  ]
}
```

按钮类型：
- `default` - 默认
- `primary` - 主要
- `danger` - 危险

#### note - 备注

```json
{
  "tag": "note",
  "elements": [
    {
      "tag": "plain_text",
      "content": "备注信息"
    }
  ]
}
```

## 事件订阅

### 消息接收事件

事件类型：`im.message.receive_v1`

```json
{
  "schema": "2.0",
  "header": {
    "event_id": "xxx",
    "event_type": "im.message.receive_v1",
    "create_time": "1706745600000",
    "token": "verification_token",
    "app_id": "cli_xxx"
  },
  "event": {
    "sender": {
      "sender_id": {
        "open_id": "ou_xxx",
        "user_id": "xxx",
        "union_id": "on_xxx"
      },
      "sender_type": "user"
    },
    "message": {
      "message_id": "om_xxx",
      "root_id": "",
      "parent_id": "",
      "create_time": "1706745600000",
      "chat_id": "oc_xxx",
      "chat_type": "group",
      "message_type": "text",
      "content": "{\"text\":\"@_user_1 你好\"}",
      "mentions": [
        {
          "key": "@_user_1",
          "id": {
            "open_id": "ou_bot"
          },
          "name": "机器人"
        }
      ]
    }
  }
}
```

### URL 验证

首次配置事件订阅时，飞书会发送验证请求：

```json
{
  "challenge": "xxx",
  "token": "verification_token",
  "type": "url_verification"
}
```

需要返回：

```json
{
  "challenge": "xxx"
}
```

## 用户 API

### 获取用户信息

```bash
GET https://open.feishu.cn/open-apis/contact/v3/users/{user_id}?user_id_type=open_id
Authorization: Bearer {tenant_access_token}
```

## 群聊 API

### 获取群信息

```bash
GET https://open.feishu.cn/open-apis/im/v1/chats/{chat_id}
Authorization: Bearer {tenant_access_token}
```

### 获取群成员

```bash
GET https://open.feishu.cn/open-apis/im/v1/chats/{chat_id}/members
Authorization: Bearer {tenant_access_token}
```

## 文件 API

### 上传图片

```bash
POST https://open.feishu.cn/open-apis/im/v1/images
Authorization: Bearer {tenant_access_token}
Content-Type: multipart/form-data

image_type: message
image: (binary)
```

### 上传文件

```bash
POST https://open.feishu.cn/open-apis/im/v1/files
Authorization: Bearer {tenant_access_token}
Content-Type: multipart/form-data

file_type: stream
file_name: example.pdf
file: (binary)
```

## 错误码

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 99991400 | 参数错误 |
| 99991401 | 无权限 |
| 99991402 | 频率限制 |
| 99991403 | 资源不存在 |

## 参考链接

- 飞书开放平台: https://open.feishu.cn/
- API 文档: https://open.feishu.cn/document/
- 消息卡片搭建工具: https://open.feishu.cn/tool/cardbuilder
