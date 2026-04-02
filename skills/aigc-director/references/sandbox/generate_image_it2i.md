# 图生图 (I2I)

使用图片生成图片（风格转换）。

## 请求

```bash
curl -X POST "http://localhost:8000/api/sandbox/i2i" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "doubao-seedream-5-0",
    "prompt": "转换为动漫风格",
    "image": "code/result/image/user_upload/photo.png"
  }'
```

## 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| model | | 模型，默认 doubao-seedream-5-0 |
| prompt | ✅ | 目标风格描述 |
| image | ✅ | 源图片路径 |

## 可用模型

| 模型 | 说明 |
|------|------|
| doubao-seedream-5-0 | 默认 |
| wan2.6-image | |

## ⚠️ 路径格式

- `image` 必须使用 `code/result/...` 格式的**相对路径**
- 禁止使用完整 URL 或本地路径

## 响应

```json
{
  "success": true,
  "image_url": "code/result/sandbox/images/xxx.png"
}
```

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `curl: (7) Failed to connect` | 后端未运行 | 启动后端服务 |
| `"error": "image not found"` | 图片路径错误 | 确认 image 路径格式为 `code/result/...` |
| `"success": false` | API Key 额度用完或无效 | 检查对应平台的 API Key |
| 风格转换效果差 | 提示词不明确 | 使用更具体的风格描述 |