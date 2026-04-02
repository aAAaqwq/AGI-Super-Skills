# 飞书消息发送

向用户发送图片、视频等媒体文件。

## 发送消息

```python
message(action="send", message="消息内容", target="user_open_id")
```

## 发送图片

```python
message(action="send", filePath="~/.openclaw/workspace/temp_imgs/xxx.png", message="图片描述", target="user_open_id")
```

## 发送视频

```python
message(action="send", filePath="~/.openclaw/workspace/temp_imgs/xxx.mp4", message="视频描述", target="user_open_id")
```

## 参数说明

| 参数 | 说明 |
|------|------|
| action | 固定为 "send" |
| message | 消息文本内容 |
| filePath | 本地文件路径（可选） |
| target | 用户 Open ID |

## ⚠️ 强制要求

1. **必须直接发送文件**：使用 `filePath` 参数直接发送，禁止只发送路径或 URL
2. **下载到本地**：生成媒体后必须先下载到 `~/.openclaw/workspace/temp_imgs/` 目录

## 下载图片示例

```python
import requests
import os

temp_dir = os.path.expanduser("~/.openclaw/workspace/temp_imgs")
os.makedirs(temp_dir, exist_ok=True)

# 从后端下载图片
url = "http://localhost:8000/code/result/image/xxx.png"
local_path = os.path.join(temp_dir, "xxx.png")

resp = requests.get(url)
with open(local_path, 'wb') as f:
    f.write(resp.content)

# 发送给用户
message(action="send", filePath=local_path, message="图片描述", target="user_open_id")
```

## ⚠️ 违规警告

- 禁止只告诉用户"图片已保存到 xxx 路径"而不发送
- 禁止只发送 URL 而不发送文件
- 违规后果：用户必须主动要求"把图片发给我"，这是严重失误！

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| 文件下载失败 | URL 错误或后端未运行 | 检查 URL 是否正确，确认后端已启动 |
| 文件太小/无效 | 下载的可能是错误页面 | 验证文件大小 > 1KB |
| 找不到文件 | 路径不存在 | 确认 `~/.openclaw/workspace/temp_imgs/` 目录下有文件 |
| message 发送失败 | user_open_id 错误 | 确认 target 参数正确 |