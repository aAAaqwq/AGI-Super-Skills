# 文生图 (T2I)

使用文字生成图片。

## 请求

```bash
curl -X POST "http://localhost:8000/api/sandbox/t2i" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "doubao-seedream-5-0",
    "prompt": "A cute cat sitting on a couch, realistic style"
  }'
```

## 可用模型

| 模型 | 说明 |
|------|------|
| doubao-seedream-5-0 | 默认 |
| wan2.6-t2i | |
| sora_image | |

## 响应

```json
{
  "success": true,
  "image_url": "code/result/sandbox/images/xxx.png"
}
```

## 注意事项

1. **提示词建议使用英文**，效果更好
2. **图片路径格式**：返回的是 `code/result/...` 格式，需要转换为实际文件路径

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `curl: (7) Failed to connect` | 后端未运行 | 启动后端服务 |
| `"success": false` | API Key 额度用完或无效 | 检查对应平台的 API Key |
| `"error": "rate limit"` | 触发限流 | 等待后重试 |
| 图片生成质量差 | 提示词不够具体 | 使用更具体的英文描述 |