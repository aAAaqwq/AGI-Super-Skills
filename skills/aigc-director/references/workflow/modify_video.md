# 修改视频生成提示词

在第五阶段完成后，用户可以修改某个分镜的视频生成提示词并重新生成视频。

## 修改分镜提示词

```bash
curl -X PATCH "http://localhost:8000/api/project/{session_id}/artifact/video_generation" \
  -H "Content-Type: application/json" \
  -d '{
    "clips": [
      {
        "scene_id": "1",
        "shot_id": "1",
        "description": "新的视频描述"
      }
    ]
  }'
```

## 重新执行视频生成

```bash
curl -X POST "http://localhost:8000/api/project/{session_id}/execute/video_generation" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "xxx"}'
```

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `curl: (7) Failed to connect` | 后端未运行 | 启动后端服务 |
| PATCH 成功但无变化 | 需要重新执行阶段 | 调用 execute/video_generation 重新生成 |
| scene_id/shot_id 不存在 | ID 错误 | 从 artifact 中获取正确的 ID |
| 视频生成失败 | 提示词不支持或超时 | 修改提示词或降低并发后重试 |