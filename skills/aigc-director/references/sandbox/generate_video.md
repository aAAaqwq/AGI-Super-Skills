# 视频生成

使用图片或文字生成视频片段（15秒以内）。

## 请求

```bash
curl -X POST "http://localhost:8000/api/sandbox/video" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wan2.6-i2v-flash",
    "prompt": "一只猫在草地上奔跑",
    "image": "code/result/image/user_upload/cat.png"
  }'
```

## 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| model | | 模型，默认 wan2.6-i2v-flash |
| prompt | ✅ | 视频描述 |
| image | ✅ | 参考图片路径 |

## 可用模型

| 模型 | 说明 |
|------|------|
| wan2.6-i2v-flash | 默认，最快 |
| wan2.6-i2v | |
| kling-v3 | |
| kling-v2-6 | |
| jimeng_ti2v_v30_pro | |

## ⚠️ 路径格式

- `image` 必须使用 `code/result/...` 格式的**相对路径**
- 禁止使用完整 URL 或本地路径

## 响应

```json
{
  "success": true,
  "video_path": "code/result/sandbox/videos/xxx.mp4",
  "record_id": "xxx"
}
```

## 获取视频文件

```python
# 直接从后端目录复制
backend_path = "/code/result/sandbox/videos/{record_id}.mp4"
local_path = "~/.openclaw/workspace/temp_imgs/{record_id}.mp4"
shutil.copy2(backend_path, local_path)
```

## 注意事项

1. 生成的视频较短（15秒以内）
2. 如果需要生成长视频，请使用完整工作流

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `curl: (7) Failed to connect` | 后端未运行 | 启动后端服务 |
| `404 Not Found` | 路径格式错误 | 使用 `code/result/...` 格式 |
| `"error": "image not found"` | 图片文件不存在 | 检查图片路径是否正确 |
| `"success": false` | API Key 额度用完或无效 | 检查对应平台的 API Key |