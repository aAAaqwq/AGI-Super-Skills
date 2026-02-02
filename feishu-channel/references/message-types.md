# 飞书消息类型说明

## 支持的消息类型

| 类型 | msg_type | 说明 |
|------|----------|------|
| 文本 | text | 纯文本消息 |
| 富文本 | post | 支持格式化的文本 |
| 图片 | image | 单张图片 |
| 文件 | file | 文件附件 |
| 语音 | audio | 语音消息 |
| 视频 | media | 视频消息 |
| 表情 | sticker | 表情包 |
| 卡片 | interactive | 交互式卡片 |
| 分享群名片 | share_chat | 群聊分享 |
| 分享用户名片 | share_user | 用户名片分享 |

## 文本消息 (text)

### 基本格式

```json
{
  "text": "Hello World"
}
```

### @用户

```json
{
  "text": "<at user_id=\"ou_xxx\">张三</at> 你好"
}
```

### @所有人

```json
{
  "text": "<at user_id=\"all\">所有人</at> 请注意"
}
```

## 富文本消息 (post)

### 基本结构

```json
{
  "zh_cn": {
    "title": "标题",
    "content": [
      [
        { "tag": "text", "text": "第一段" }
      ],
      [
        { "tag": "text", "text": "第二段" }
      ]
    ]
  }
}
```

### 支持的标签

#### text - 文本

```json
{
  "tag": "text",
  "text": "普通文本",
  "un_escape": false
}
```

#### a - 链接

```json
{
  "tag": "a",
  "text": "点击查看",
  "href": "https://example.com"
}
```

#### at - @用户

```json
{
  "tag": "at",
  "user_id": "ou_xxx",
  "user_name": "张三"
}
```

#### img - 图片

```json
{
  "tag": "img",
  "image_key": "img_xxx",
  "width": 300,
  "height": 200
}
```

### 完整示例

```json
{
  "zh_cn": {
    "title": "项目周报",
    "content": [
      [
        { "tag": "text", "text": "本周完成情况：" }
      ],
      [
        { "tag": "text", "text": "1. 完成了 " },
        { "tag": "a", "text": "需求文档", "href": "https://example.com/doc" }
      ],
      [
        { "tag": "text", "text": "2. 修复了 5 个 Bug" }
      ],
      [
        { "tag": "text", "text": "请 " },
        { "tag": "at", "user_id": "ou_xxx", "user_name": "张三" },
        { "tag": "text", "text": " 审核" }
      ]
    ]
  }
}
```

## 图片消息 (image)

```json
{
  "image_key": "img_xxx"
}
```

需要先通过上传接口获取 image_key。

## 文件消息 (file)

```json
{
  "file_key": "file_xxx"
}
```

需要先通过上传接口获取 file_key。

## 卡片消息 (interactive)

卡片消息是最灵活的消息类型，支持丰富的布局和交互。

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

### 常用元素

#### 文本块 (div)

```json
{
  "tag": "div",
  "text": {
    "tag": "lark_md",
    "content": "**粗体** _斜体_ ~~删除线~~"
  }
}
```

#### 多列布局 (column_set)

```json
{
  "tag": "column_set",
  "flex_mode": "none",
  "background_style": "default",
  "columns": [
    {
      "tag": "column",
      "width": "weighted",
      "weight": 1,
      "elements": [
        {
          "tag": "div",
          "text": {
            "tag": "plain_text",
            "content": "左列"
          }
        }
      ]
    },
    {
      "tag": "column",
      "width": "weighted",
      "weight": 1,
      "elements": [
        {
          "tag": "div",
          "text": {
            "tag": "plain_text",
            "content": "右列"
          }
        }
      ]
    }
  ]
}
```

#### 按钮 (button)

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
        "action": "confirm"
      }
    },
    {
      "tag": "button",
      "text": {
        "tag": "plain_text",
        "content": "取消"
      },
      "type": "default"
    }
  ]
}
```

#### 图片 (img)

```json
{
  "tag": "img",
  "img_key": "img_xxx",
  "alt": {
    "tag": "plain_text",
    "content": "图片描述"
  }
}
```

### 完整卡片示例

```json
{
  "config": {
    "wide_screen_mode": true
  },
  "header": {
    "title": {
      "tag": "plain_text",
      "content": "🎉 任务完成通知"
    },
    "template": "green"
  },
  "elements": [
    {
      "tag": "div",
      "text": {
        "tag": "lark_md",
        "content": "**任务名称**: 数据同步\n**完成时间**: 2024-02-01 10:30\n**处理记录**: 1,234 条"
      }
    },
    {
      "tag": "hr"
    },
    {
      "tag": "action",
      "actions": [
        {
          "tag": "button",
          "text": {
            "tag": "plain_text",
            "content": "查看详情"
          },
          "type": "primary",
          "url": "https://example.com/task/123"
        }
      ]
    },
    {
      "tag": "note",
      "elements": [
        {
          "tag": "plain_text",
          "content": "由 OpenClaw 自动发送"
        }
      ]
    }
  ]
}
```

## Markdown 语法 (lark_md)

在卡片消息中使用 `lark_md` 标签时，支持以下 Markdown 语法：

| 语法 | 效果 |
|------|------|
| `**text**` | **粗体** |
| `_text_` | _斜体_ |
| `~~text~~` | ~~删除线~~ |
| `[text](url)` | 链接 |
| `<at id=xxx></at>` | @用户 |

## 消息接收解析

### 文本消息

```json
{
  "message_type": "text",
  "content": "{\"text\":\"Hello\"}"
}
```

解析：
```javascript
const content = JSON.parse(message.content);
const text = content.text; // "Hello"
```

### 带 @提及的消息

```json
{
  "message_type": "text",
  "content": "{\"text\":\"@_user_1 你好\"}",
  "mentions": [
    {
      "key": "@_user_1",
      "id": {
        "open_id": "ou_xxx"
      },
      "name": "机器人"
    }
  ]
}
```

解析：
```javascript
const content = JSON.parse(message.content);
let text = content.text; // "@_user_1 你好"

// 移除 @提及占位符
for (const mention of message.mentions) {
  text = text.replace(mention.key, '').trim();
}
// text = "你好"
```

## 参考链接

- 消息类型文档: https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/im-v1/message/create_json
- 卡片搭建工具: https://open.feishu.cn/tool/cardbuilder
